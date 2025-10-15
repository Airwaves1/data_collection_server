from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from datetime import datetime
import os
import zipfile
import threading
import time
import uuid
import shutil
import re
from .models import (
    Collector, TaskInfo, Observations, Parameters, 
    SkeletonData, KinematicData, IMUData, TactileFeedback
)
from .serializers import (
    CollectorSerializer, CollectorCreateUpdateSerializer, CollectorCreateSerializer, CollectorLoginSerializer,
    TaskInfoSerializer, TaskInfoCreateSerializer,
    ObservationsSerializer, ParametersSerializer,
    SkeletonDataSerializer, KinematicDataSerializer,
    IMUDataSerializer, TactileFeedbackSerializer
)


class CollectorViewSet(viewsets.ModelViewSet):
    """采集者管理API"""
    queryset = Collector.objects.all()
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return CollectorCreateUpdateSerializer
        elif self.action == 'register':
            return CollectorCreateSerializer
        elif self.action == 'login':
            return CollectorLoginSerializer
        return CollectorSerializer
    
    @action(detail=False, methods=['post'])
    def register(self, request):
        """用户注册"""
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            # 检查用户名是否已存在
            if Collector.objects.filter(username=serializer.validated_data['username']).exists():
                return Response({'error': '用户名已存在'}, status=status.HTTP_400_BAD_REQUEST)
            
            # 检查collector_id是否已存在
            if Collector.objects.filter(collector_id=serializer.validated_data['collector_id']).exists():
                return Response({'error': '采集者ID已存在'}, status=status.HTTP_400_BAD_REQUEST)
            
            collector = serializer.save()
            return Response({
                'message': '注册成功',
                'collector_id': collector.id,
                'username': collector.username
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def login(self, request):
        """用户登录"""
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            username = serializer.validated_data['username']
            password = serializer.validated_data['password']
            
            try:
                collector = Collector.objects.get(username=username, password=password)
                return Response({
                    'message': '登录成功',
                    'collector_id': collector.id,
                    'username': collector.username,
                    'collector_name': collector.collector_name,
                    'collector_organization': collector.collector_organization
                }, status=status.HTTP_200_OK)
            except Collector.DoesNotExist:
                return Response({'error': '用户名或密码错误'}, status=status.HTTP_401_UNAUTHORIZED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def list_collectors(self, request):
        """获取采集者列表 - 对应DBController.list_collectors"""
        limit = int(request.query_params.get('limit', 200))
        offset = int(request.query_params.get('offset', 0))
        
        collectors = Collector.objects.all()[offset:offset + limit]
        serializer = self.get_serializer(collectors, many=True)
        return Response(serializer.data)
    
    def upsert_collector(self, collector_data):
        """创建或更新采集者 - 对应DBController.upsert_collector"""
        collector_id = collector_data.get('collector_id')
        
        try:
            # 尝试根据collector_id查找现有记录
            existing_collector = Collector.objects.get(collector_id=collector_id)
            # 更新现有记录
            serializer = CollectorCreateUpdateSerializer(existing_collector, data=collector_data)
            if serializer.is_valid():
                serializer.save()
                return existing_collector.id
        except Collector.DoesNotExist:
            # 创建新记录
            serializer = CollectorCreateUpdateSerializer(data=collector_data)
            if serializer.is_valid():
                collector = serializer.save()
                return collector.id
        
        return None


class TaskInfoViewSet(viewsets.ModelViewSet):
    """任务信息管理API"""
    queryset = TaskInfo.objects.all()
    
    def get_serializer_class(self):
        if self.action in ['create']:
            return TaskInfoCreateSerializer
        return TaskInfoSerializer
    
    @action(detail=False, methods=['get'])
    def by_collector(self, request):
        """根据采集者ID获取任务列表 - 对应DBController.list_tasks_by_collector"""
        collector_id = request.query_params.get('collector_id')
        limit = int(request.query_params.get('limit', 100))
        offset = int(request.query_params.get('offset', 0))
        
        tasks = TaskInfo.objects.filter(collector_id=collector_id)[offset:offset + limit]
        serializer = self.get_serializer(tasks, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_episode(self, request):
        """根据episode_id获取任务信息 - 对应DBController.get_task_info_by_episode"""
        episode_id = request.query_params.get('episode_id')
        task = get_object_or_404(TaskInfo, episode_id=episode_id)
        serializer = self.get_serializer(task)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_task_id(self, request):
        """根据业务task_id获取任务信息 - 对应DBController.get_task_info_by_task_id"""
        task_id = request.query_params.get('task_id')
        # 根据task_id查询，返回最新的记录
        tasks = TaskInfo.objects.filter(task_id=task_id).order_by('-id')
        if not tasks.exists():
            return Response({'error': 'Task not found'}, status=404)
        
        # 返回最新的任务记录
        task = tasks.first()
        serializer = self.get_serializer(task)
        return Response(serializer.data)
    
    def create_task_info(self, task_data):
        """创建任务信息 - 对应DBController.create_task_info"""
        print(f"[DEBUG] create_task_info 收到数据: {task_data}")
        serializer = TaskInfoCreateSerializer(data=task_data)
        print(f"[DEBUG] 序列化器是否有效: {serializer.is_valid()}")
        if not serializer.is_valid():
            print(f"[DEBUG] 序列化器错误: {serializer.errors}")
            return None
        
        task = serializer.save()
        # 保存后设置episode_id为task的ID
        task.episode_id = str(task.id)
        task.save()
        print(f"[DEBUG] 成功保存任务: {task}, episode_id设置为: {task.episode_id}")
        return task.id
    
    @action(detail=True, methods=['patch'])
    def update_links(self, request, pk=None):
        """更新任务信息的外键链接 - 对应DBController.update_task_info_links"""
        task = self.get_object()
        links = request.data
        
        # 更新外键字段
        for field_name, field_value in links.items():
            if hasattr(task, field_name):
                setattr(task, field_name, field_value)
        
        task.save()
        serializer = self.get_serializer(task)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def save_full_episode(self, request):
        """保存完整episode - 对应DBController.save_full_episode"""
        data = request.data
        print(f"[DEBUG] 收到保存请求数据: {data}")
        
        collector_id = data.get('collector_id')
        episode_id = data.get('episode_id')
        task_name = data.get('task_name')
        task_id_external = data.get('task_id')  # 业务任务ID
        init_scene_text = data.get('init_scene_text', '')
        action_config = data.get('action_config', [])
        task_status = data.get('task_status', 'pending')  # 默认为待审核状态
        
        print(f"[DEBUG] 解析参数: collector_id={collector_id}, episode_id={episode_id}, task_name={task_name}")
        
        # 验证采集者是否存在
        try:
            collector = Collector.objects.get(id=collector_id)
            print(f"[DEBUG] 找到采集者: {collector}")
        except Collector.DoesNotExist:
            print(f"[DEBUG] 采集者ID {collector_id} 不存在")
            return Response({'error': f'采集者ID {collector_id} 不存在'}, status=status.HTTP_400_BAD_REQUEST)
        
        task_data = {
            'collector': collector_id,  # 使用collector字段名（外键）
            'task_id': task_id_external,
            'task_name': task_name,
            'init_scene_text': init_scene_text,
            'action_config': action_config,
            'task_status': task_status,
        }
        
        print(f"[DEBUG] 准备创建任务数据: {task_data}")
        
        task_id = self.create_task_info(task_data)
        if task_id:
            print(f"[DEBUG] 成功创建任务，ID: {task_id}")
            return Response({'task_id': task_id, 'episode_id': task_id}, status=status.HTTP_201_CREATED)
        
        print(f"[DEBUG] 创建任务失败")
        return Response({'error': '创建任务失败'}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['patch'])
    def update_status(self, request, pk=None):
        """更新任务状态"""
        task = self.get_object()
        new_status = request.data.get('task_status')
        
        if new_status not in ['pending', 'accepted', 'rejected', 'ng']:
            return Response({'error': '无效的任务状态'}, status=status.HTTP_400_BAD_REQUEST)
        
        task.task_status = new_status
        task.save()
        
        serializer = self.get_serializer(task)
        return Response(serializer.data)
    
    @action(detail=False, methods=['patch'])
    def update_by_task_id(self, request):
        """根据业务task_id更新任务信息"""
        task_id = request.data.get('task_id')
        if not task_id:
            return Response({'error': '缺少task_id'}, status=status.HTTP_400_BAD_REQUEST)
        
        # 查找最新的任务记录
        tasks = TaskInfo.objects.filter(task_id=task_id).order_by('-id')
        if not tasks.exists():
            return Response({'error': '任务不存在'}, status=status.HTTP_404_NOT_FOUND)
        
        task = tasks.first()
        
        # 更新字段
        update_fields = ['task_name', 'init_scene_text', 'action_config', 'task_status']
        for field in update_fields:
            if field in request.data:
                setattr(task, field, request.data[field])
        
        task.save()
        
        serializer = self.get_serializer(task)
        return Response(serializer.data)


class ObservationsViewSet(viewsets.ModelViewSet):
    """观察数据管理API"""
    queryset = Observations.objects.all()
    serializer_class = ObservationsSerializer
    
    def create_observations(self, obs_data):
        """创建观察数据 - 对应DBController.create_observations"""
        serializer = self.get_serializer(data=obs_data)
        if serializer.is_valid():
            obs = serializer.save()
            return obs.id
        return None


class ParametersViewSet(viewsets.ModelViewSet):
    """参数数据管理API"""
    queryset = Parameters.objects.all()
    serializer_class = ParametersSerializer
    
    def create_parameters(self, params_data):
        """创建参数数据 - 对应DBController.create_parameters"""
        serializer = self.get_serializer(data=params_data)
        if serializer.is_valid():
            params = serializer.save()
            return params.id
        return None


class SkeletonDataViewSet(viewsets.ModelViewSet):
    """骨骼数据管理API"""
    queryset = SkeletonData.objects.all()
    serializer_class = SkeletonDataSerializer
    
    def create_skeleton_data(self, data):
        """创建骨骼数据 - 对应DBController.create_skeleton_data"""
        serializer = self.get_serializer(data=data)
        if serializer.is_valid():
            skeleton_data = serializer.save()
            return skeleton_data.id
        return None


class KinematicDataViewSet(viewsets.ModelViewSet):
    """运动学数据管理API"""
    queryset = KinematicData.objects.all()
    serializer_class = KinematicDataSerializer
    
    def create_kinematic_data(self, data):
        """创建运动学数据 - 对应DBController.create_kinematic_data"""
        serializer = self.get_serializer(data=data)
        if serializer.is_valid():
            kinematic_data = serializer.save()
            return kinematic_data.id
        return None


class IMUDataViewSet(viewsets.ModelViewSet):
    """IMU数据管理API"""
    queryset = IMUData.objects.all()
    serializer_class = IMUDataSerializer
    
    def create_imu(self, imu_data):
        """创建IMU数据 - 对应DBController.create_imu"""
        serializer = self.get_serializer(data=imu_data)
        if serializer.is_valid():
            imu = serializer.save()
            return imu.id
        return None


class TactileFeedbackViewSet(viewsets.ModelViewSet):
    """触觉反馈数据管理API"""
    queryset = TactileFeedback.objects.all()
    serializer_class = TactileFeedbackSerializer
    
    def create_tactile_feedback(self, tf_data):
        """创建触觉反馈数据 - 对应DBController.create_tactile_feedback"""
        serializer = self.get_serializer(data=tf_data)
        if serializer.is_valid():
            tf = serializer.save()
            return tf.id
        return None


# 业务逻辑控制器 - 对应原DBController的功能
class DataCollectionController:
    """数据采集业务控制器"""
    
    def __init__(self):
        self.collector_viewset = CollectorViewSet()
        self.task_viewset = TaskInfoViewSet()
        self.observations_viewset = ObservationsViewSet()
        self.parameters_viewset = ParametersViewSet()
        self.skeleton_viewset = SkeletonDataViewSet()
        self.kinematic_viewset = KinematicDataViewSet()
        self.imu_viewset = IMUDataViewSet()
        self.tactile_viewset = TactileFeedbackViewSet()
    
    def upsert_collector(self, collector_data):
        """创建或更新采集者"""
        return self.collector_viewset.upsert_collector(collector_data)
    
    def get_collector(self, collector_id):
        """获取采集者信息"""
        try:
            collector = Collector.objects.get(id=collector_id)
            serializer = CollectorSerializer(collector)
            return serializer.data
        except Collector.DoesNotExist:
            return None
    
    def list_collectors(self, limit=200, offset=0):
        """获取采集者列表"""
        collectors = Collector.objects.all()[offset:offset + limit]
        serializer = CollectorSerializer(collectors, many=True)
        return serializer.data
    
    def create_task_info(self, task_data):
        """创建任务信息"""
        return self.task_viewset.create_task_info(task_data)
    
    def update_task_info_links(self, task_info_id, links):
        """更新任务信息的外键链接"""
        try:
            task = TaskInfo.objects.get(id=task_info_id)
            for field_name, field_value in links.items():
                if hasattr(task, field_name):
                    setattr(task, field_name, field_value)
            task.save()
        except TaskInfo.DoesNotExist:
            pass
    
    def get_task_info_by_episode(self, episode_id):
        """根据episode_id获取任务信息"""
        try:
            task = TaskInfo.objects.get(episode_id=episode_id)
            serializer = TaskInfoSerializer(task)
            return serializer.data
        except TaskInfo.DoesNotExist:
            return None
    
    def list_tasks_by_collector(self, collector_id, limit=100, offset=0):
        """根据采集者ID获取任务列表"""
        tasks = TaskInfo.objects.filter(collector_id=collector_id)[offset:offset + limit]
        serializer = TaskInfoSerializer(tasks, many=True)
        return serializer.data
    
    def create_observations(self, obs_data):
        """创建观察数据"""
        return self.observations_viewset.create_observations(obs_data)
    
    def create_parameters(self, params_data):
        """创建参数数据"""
        return self.parameters_viewset.create_parameters(params_data)
    
    def create_skeleton_data(self, data):
        """创建骨骼数据"""
        return self.skeleton_viewset.create_skeleton_data(data)
    
    def create_kinematic_data(self, data):
        """创建运动学数据"""
        return self.kinematic_viewset.create_kinematic_data(data)
    
    def create_imu(self, imu_data):
        """创建IMU数据"""
        return self.imu_viewset.create_imu(imu_data)
    
    def create_tactile_feedback(self, tf_data):
        """创建触觉反馈数据"""
        return self.tactile_viewset.create_tactile_feedback(tf_data)
    
    def save_full_episode(self, collector_id, episode_id, task_name, init_scene_text, action_config):
        """保存完整episode"""
        task_data = {
            'collector_id': collector_id,
            'episode_id': episode_id,
            'task_name': task_name,
            'init_scene_text': init_scene_text,
            'action_config': action_config,
            'created_at': datetime.now(),
            'completed_at': None,
        }
        return self.create_task_info(task_data)


class FileUploadViewSet(viewsets.ViewSet):
    """文件上传管理API"""
    
    # 类级别的共享状态
    _active_extractions = {}  # 存储活跃的解压任务
    _extraction_queue = []     # 解压任务队列
    _max_concurrent_extractions = 2  # 最大并发解压数
    _running_extractions = 0  # 当前运行解压数
    _extraction_thread = None  # 解压处理线程
    _thread_started = False  # 线程启动标志
    
    @classmethod
    def _ensure_thread_started(cls):
        """确保解压线程已启动"""
        if not cls._thread_started:
            cls._extraction_thread = threading.Thread(target=cls._process_extraction_queue, daemon=True)
            cls._extraction_thread.start()
            cls._thread_started = True
    
    @classmethod
    def _process_extraction_queue(cls):
        """处理解压队列"""
        while True:
            try:
                if cls._extraction_queue and cls._running_extractions < cls._max_concurrent_extractions:
                    task = cls._extraction_queue.pop(0)
                    cls._running_extractions += 1
                    
                    # 在新线程中执行解压任务
                    extraction_thread = threading.Thread(target=cls._execute_extraction, args=(task,))
                    extraction_thread.start()
                
                time.sleep(0.5)  # 避免CPU占用过高
            except Exception as e:
                print(f"[FileUpload] 解压队列处理错误: {e}")
    
    @classmethod
    def _execute_extraction(cls, task):
        """执行解压任务"""
        try:
            print(f"[FileUpload] 开始解压任务: {task['task_id']}")
            task['status'] = 'extracting'
            
            # 解压文件
            zip_path = task['zip_path']
            extract_path = task['extract_path']
            
            # 确保解压目录存在
            os.makedirs(extract_path, exist_ok=True)
            
            with zipfile.ZipFile(zip_path, 'r') as zipf:
                zipf.extractall(extract_path)
            
            print(f"[FileUpload] 解压完成: {extract_path}")
            
            # 解压完成后：基于解压目录生成数据库记录并写入相对路径
            try:
                cls._generate_models_from_extracted_folder(extract_path)
            except Exception as gen_e:
                print(f"[FileUpload] 生成数据模型记录失败: {gen_e}")
            
            # 删除压缩包
            try:
                os.remove(zip_path)
                print(f"[FileUpload] 删除压缩包: {zip_path}")
            except Exception as e:
                print(f"[FileUpload] 删除压缩包失败: {e}")
            
            task['status'] = 'completed'
            task['completed_at'] = datetime.now()
            print(f"[FileUpload] 解压任务完成: {task['task_id']}")
            
        except Exception as e:
            task['status'] = 'failed'
            task['error_message'] = str(e)
            task['completed_at'] = datetime.now()
            print(f"[FileUpload] 解压任务失败: {task['task_id']}, 错误: {e}")
            
            # 清理失败的任务文件
            try:
                if os.path.exists(task['zip_path']):
                    os.remove(task['zip_path'])
            except Exception as cleanup_e:
                print(f"[FileUpload] 清理失败文件错误: {cleanup_e}")
        
        finally:
            cls._running_extractions -= 1

    @classmethod
    def _generate_models_from_extracted_folder(cls, extract_path: str):
        """从解压后的目录生成并保存各数据模型，更新TaskInfo外键链接。
        目录命名: taskname_taskid_episode_id
        子目录: IMU, kinematic, parameters, skeleton, Tactile, video
        
        说明:
        - 仅在能找到对应的TaskInfo(优先episode_id)时写库；若找不到则跳过但打印告警。
        - 写入路径均为相对settings.FILE_UPLOAD_DIR的相对路径。
        - Observations.depth_path 暂为空。
        """
        base_upload_dir = getattr(settings, 'FILE_UPLOAD_DIR', 'uploads')
        folder_name = os.path.basename(extract_path.rstrip(os.sep))
        # 解析 task_name, task_id, episode_id
        task_name, external_task_id, episode_id = cls._parse_folder_triplet(folder_name)
        if not (task_name and external_task_id and episode_id):
            print(f"[FileUpload] 警告: 目录名不符合规范, 跳过写库: {folder_name}")
            return

        # 查找TaskInfo(优先episode_id)，否则尝试按task_id取最近的一条
        task = None
        try:
            task = TaskInfo.objects.get(episode_id=episode_id)
        except TaskInfo.DoesNotExist:
            tasks = TaskInfo.objects.filter(task_id=external_task_id).order_by('-id')
            if tasks.exists():
                task = tasks.first()
        if task is None:
            print(f"[FileUpload] 警告: 未找到TaskInfo(episode_id={episode_id}, task_id={external_task_id}), 跳过写库")
            return

        # 构建各子目录路径(大小写不敏感匹配)
        subdirs = cls._map_existing_subdirs(extract_path, [
            'IMU', 'kinematic', 'parameters', 'skeleton', 'Tactile', 'video'
        ])

        with transaction.atomic():
            # Observations: video_path 取首个视频文件，depth_path 空
            obs_id = None
            video_file = cls._find_first_file_with_exts(subdirs.get('video'), ['.mp4', '.avi', '.mov', '.mkv'])
            if video_file:
                rel_video = cls._safe_relpath(video_file, base_upload_dir)
                obs = Observations.objects.create(
                    task_info=task,
                    episode_id=task.episode_id,
                    video_path=rel_video,
                    depth_path=""
                )
                obs_id = obs.id

            # Parameters: 取首个参数文件
            params_id = None
            params_file = cls._find_first_file_with_exts(subdirs.get('parameters'), ['.json', '.yaml', '.yml', '.txt'])
            if params_file:
                rel_params = cls._safe_relpath(params_file, base_upload_dir)
                params = Parameters.objects.create(
                    task_info=task,
                    episode_id=task.episode_id,
                    parameters_path=rel_params
                )
                params_id = params.id

            # SkeletonData: 分别选取对应扩展名
            skel_id = None
            fbx = cls._find_first_file_with_exts(subdirs.get('skeleton'), ['.fbx'])
            bvh = cls._find_first_file_with_exts(subdirs.get('skeleton'), ['.bvh'])
            csv = cls._find_first_file_with_exts(subdirs.get('skeleton'), ['.csv'])
            npy = cls._find_first_file_with_exts(subdirs.get('skeleton'), ['.npy'])
            if any([fbx, bvh, csv, npy]):
                skel = SkeletonData.objects.create(
                    task_info=task,
                    episode_id=task.episode_id,
                    fbx_path=cls._safe_relpath(fbx, base_upload_dir) if fbx else "",
                    bvh_path=cls._safe_relpath(bvh, base_upload_dir) if bvh else "",
                    csv_path=cls._safe_relpath(csv, base_upload_dir) if csv else "",
                    npy_path=cls._safe_relpath(npy, base_upload_dir) if npy else "",
                )
                skel_id = skel.id

            # KinematicData: 记录目录本身(相对路径)
            kine_id = None
            if subdirs.get('kinematic') and os.path.isdir(subdirs['kinematic']):
                rel_kine = cls._safe_relpath(subdirs['kinematic'], base_upload_dir)
                kine = KinematicData.objects.create(
                    task_info=task,
                    episode_id=task.episode_id,
                    path=rel_kine
                )
                kine_id = kine.id

            # IMUData: left/right 优先匹配, 否则取前两个
            imu_id = None
            left_imu, right_imu = cls._pick_left_right_files(subdirs.get('IMU'))
            if left_imu or right_imu:
                imu = IMUData.objects.create(
                    task_info=task,
                    episode_id=task.episode_id,
                    leftHandIMU_path=cls._safe_relpath(left_imu, base_upload_dir) if left_imu else "",
                    rightHandIMU_path=cls._safe_relpath(right_imu, base_upload_dir) if right_imu else "",
                )
                imu_id = imu.id

            # TactileFeedback: left/right 优先匹配
            tac_id = None
            left_tac, right_tac = cls._pick_left_right_files(subdirs.get('Tactile'))
            if left_tac or right_tac:
                tac = TactileFeedback.objects.create(
                    task_info=task,
                    episode_id=task.episode_id,
                    leftHandTac_path=cls._safe_relpath(left_tac, base_upload_dir) if left_tac else "",
                    rightHandTac_path=cls._safe_relpath(right_tac, base_upload_dir) if right_tac else "",
                )
                tac_id = tac.id

            # 回填 TaskInfo 链接字段
            updated = False
            if obs_id is not None:
                task.observations_id = obs_id; updated = True
            if params_id is not None:
                task.parameters_id = params_id; updated = True
            if skel_id is not None:
                task.skeletonData_id = skel_id; updated = True
            if kine_id is not None:
                task.kinematicData_id = kine_id; updated = True
            if imu_id is not None:
                task.imu_id = imu_id; updated = True
            if tac_id is not None:
                task.tactile_feedback_id = tac_id; updated = True
            if updated:
                task.save()

    @staticmethod
    def _parse_folder_triplet(folder_name: str):
        parts = folder_name.split('_') if folder_name else []
        if len(parts) >= 3:
            # 只取最后两段作为task_id与episode_id，其余前缀合并为task_name
            task_name = '_'.join(parts[:-2])
            task_id = parts[-2]
            episode_id = parts[-1]
            return task_name, task_id, episode_id
        return None, None, None

    @staticmethod
    def _safe_relpath(path: str, base_root: str):
        if not path:
            return ""
        try:
            # 使用os.path.relpath获取相对路径，然后统一使用正斜杠（URL兼容）
            rel_path = os.path.relpath(path, base_root)
            # 跨平台：将路径分隔符统一为正斜杠（适用于URL和跨平台）
            return rel_path.replace(os.sep, '/')
        except Exception:
            # 如果计算相对路径失败，直接转换分隔符
            return path.replace(os.sep, '/')

    @staticmethod
    def _map_existing_subdirs(root: str, names: list):
        # 大小写不敏感匹配
        result = {}
        try:
            entries = os.listdir(root)
        except Exception:
            entries = []
        lower_to_real = {e.lower(): e for e in entries}
        for n in names:
            real = lower_to_real.get(n.lower())
            if real:
                result[n] = os.path.join(root, real)
            else:
                result[n] = None
        return result

    @staticmethod
    def _find_first_file_with_exts(root: str, exts: list):
        if not root or not os.path.isdir(root):
            return None
        exts_lower = [e.lower() for e in exts]
        for dirpath, _, filenames in os.walk(root):
            for fn in sorted(filenames):
                if os.path.splitext(fn)[1].lower() in exts_lower:
                    return os.path.join(dirpath, fn)
        return None

    @staticmethod
    def _pick_left_right_files(root: str):
        """在目录中挑选左右手文件，优先匹配文件名包含 left/right 或 L/R 关键字；否则取前两个文件。"""
        if not root or not os.path.isdir(root):
            return None, None
        files = []
        for dirpath, _, filenames in os.walk(root):
            for fn in sorted(filenames):
                files.append(os.path.join(dirpath, fn))
        if not files:
            return None, None
        left = None
        right = None
        for f in files:
            name = os.path.basename(f).lower()
            if left is None and ('left' in name or name.startswith('l_') or name.endswith('_l')):
                left = f
            elif right is None and ('right' in name or name.startswith('r_') or name.endswith('_r')):
                right = f
        if left is None and len(files) >= 1:
            left = files[0]
        if right is None and len(files) >= 2:
            right = files[1]
        return left, right
    
    @action(detail=False, methods=['post'])
    def upload(self, request):
        """接收文件上传"""
        try:
            # 确保解压线程已启动
            self._ensure_thread_started()
            
            # 获取上传的文件
            file_obj = request.FILES.get('file')
            if not file_obj:
                return Response({'error': '没有上传文件'}, status=status.HTTP_400_BAD_REQUEST)
            
            # 获取其他参数
            task_id = request.data.get('task_id', '')
            device_id = request.data.get('device_id', '')
            auth_token = request.data.get('auth_token', '')
            
            # 简单的认证检查（可以根据需要扩展）
            if not auth_token:
                return Response({'error': '缺少认证令牌'}, status=status.HTTP_401_UNAUTHORIZED)
            
            # 生成唯一的上传ID
            upload_id = f"upload_{int(time.time())}_{uuid.uuid4().hex[:8]}"
            
            # 设置文件存储路径
            upload_dir = getattr(settings, 'FILE_UPLOAD_DIR', 'uploads')
            zip_filename = f"{upload_id}.zip"
            zip_path = os.path.join(upload_dir, zip_filename)
            
            # 确保上传目录存在
            os.makedirs(upload_dir, exist_ok=True)
            
            # 保存上传的文件
            with open(zip_path, 'wb') as f:
                for chunk in file_obj.chunks():
                    f.write(chunk)
            
            print(f"[FileUpload] 文件上传成功: {zip_path}, 大小: {file_obj.size} bytes")
            
            # 从ZIP文件名中提取原始文件夹名称
            # ZIP文件名格式: folder_name_upload_timestamp_random.zip
            original_filename = file_obj.name
            if '_' in original_filename and original_filename.endswith('.zip'):
                # 去掉.zip后缀
                name_without_ext = original_filename[:-4]
                parts = name_without_ext.split('_')
                
                # 找到upload_开头的部分，去掉它和后面的部分
                upload_index = -1
                for i, part in enumerate(parts):
                    if part == 'upload':
                        upload_index = i
                        break
                
                if upload_index > 0:
                    # 提取upload之前的部分作为文件夹名称
                    folder_name = '_'.join(parts[:upload_index])
                else:
                    folder_name = upload_id
            else:
                folder_name = upload_id
            
            # 创建解压任务
            extract_path = os.path.join(upload_dir, folder_name)
            extraction_task = {
                'task_id': upload_id,
                'zip_path': zip_path,
                'extract_path': extract_path,
                'status': 'queued',
                'created_at': datetime.now(),
                'completed_at': None,
                'error_message': '',
                'device_id': device_id,
                'original_task_id': task_id
            }
            
            self._active_extractions[upload_id] = extraction_task
            self._extraction_queue.append(extraction_task)
            
            return Response({
                'upload_id': upload_id,
                'status': 'uploaded',
                'message': '文件上传成功，正在解压...',
                'file_size': file_obj.size
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            print(f"[FileUpload] 上传处理错误: {e}")
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def status(self, request):
        """查询解压状态"""
        upload_id = request.query_params.get('upload_id')
        if not upload_id:
            return Response({'error': '缺少upload_id参数'}, status=status.HTTP_400_BAD_REQUEST)
        
        if upload_id in self._active_extractions:
            task = self._active_extractions[upload_id]
            return Response({
                'upload_id': task['task_id'],
                'status': task['status'],
                'created_at': task['created_at'].isoformat(),
                'completed_at': task['completed_at'].isoformat() if task['completed_at'] else None,
                'error_message': task['error_message'],
                'extract_path': task['extract_path'] if task['status'] == 'completed' else None
            })
        else:
            return Response({'error': '上传任务不存在'}, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=False, methods=['get'])
    def list_uploads(self, request):
        """列出所有上传任务"""
        limit = int(request.query_params.get('limit', 50))
        offset = int(request.query_params.get('offset', 0))
        
        # 获取任务列表
        tasks = list(self._active_extractions.values())
        tasks.sort(key=lambda x: x['created_at'], reverse=True)
        
        # 分页
        paginated_tasks = tasks[offset:offset + limit]
        
        # 格式化返回数据
        result = []
        for task in paginated_tasks:
            result.append({
                'upload_id': task['task_id'],
                'status': task['status'],
                'created_at': task['created_at'].isoformat(),
                'completed_at': task['completed_at'].isoformat() if task['completed_at'] else None,
                'device_id': task['device_id'],
                'original_task_id': task['original_task_id']
            })
        
        return Response({
            'uploads': result,
            'total': len(tasks),
            'limit': limit,
            'offset': offset
        })
    
    @action(detail=False, methods=['delete'])
    def cleanup(self, request):
        """清理完成的任务"""
        try:
            cleaned_count = 0
            current_time = datetime.now()
            
            # 清理超过1小时的已完成任务
            tasks_to_remove = []
            for upload_id, task in self._active_extractions.items():
                if (task['status'] in ['completed', 'failed'] and 
                    task['completed_at'] and 
                    (current_time - task['completed_at']).seconds > 3600):
                    tasks_to_remove.append(upload_id)
            
            for upload_id in tasks_to_remove:
                del self._active_extractions[upload_id]
                cleaned_count += 1
            
            return Response({
                'message': f'清理了 {cleaned_count} 个过期任务',
                'cleaned_count': cleaned_count
            })
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'])
    def info(self, request):
        """获取上传服务信息"""
        return Response({
            'service_name': 'File Upload Service',
            'active_extractions': len(self._active_extractions),
            'running_extractions': self._running_extractions,
            'queue_length': len(self._extraction_queue),
            'max_concurrent_extractions': self._max_concurrent_extractions,
            'upload_dir': getattr(settings, 'FILE_UPLOAD_DIR', 'uploads')
        })


class ExportViewSet(viewsets.ViewSet):
    """数据导出API"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._active_exports = {}
        self._export_queue = []
        self._running_exports = 0
        self._max_concurrent_exports = 2
    
    @action(detail=False, methods=['post'])
    def export_all(self, request):
        """导出所有uploads下的数据到标准目录结构"""
        try:
            # 生成导出任务ID
            export_id = f"export_{int(time.time())}_{uuid.uuid4().hex[:8]}"
            
            # 创建导出任务
            export_task = {
                'export_id': export_id,
                'status': 'queued',
                'progress': 0,
                'message': '等待处理',
                'created_at': datetime.now(),
                'completed_at': None,
                'error_message': '',
                'export_path': '',
                'file_count': 0
            }
            
            self._active_exports[export_id] = export_task
            self._export_queue.append(export_task)
            
            # 启动导出线程
            export_thread = threading.Thread(target=self._execute_export, args=(export_task,))
            export_thread.start()
            
            return Response({
                'export_id': export_id,
                'status': 'queued',
                'message': '导出任务已创建'
            })
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _execute_export(self, export_task):
        """执行导出任务"""
        try:
            export_task['status'] = 'preparing'
            export_task['message'] = '准备导出...'
            
            # 生成导出目录名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            export_dir_name = f"CMAvatar_data_{timestamp}"
            
            # 设置导出路径
            base_dir = os.path.join(settings.BASE_DIR, 'export_output')
            export_path = os.path.join(base_dir, export_dir_name)
            
            # 创建导出目录
            os.makedirs(export_path, exist_ok=True)
            export_task['export_path'] = export_path
            
            # 扫描uploads目录
            uploads_dir = os.path.join(settings.BASE_DIR, 'uploads')
            if not os.path.exists(uploads_dir):
                raise Exception("uploads目录不存在")
            
            # 获取所有任务目录
            task_dirs = [d for d in os.listdir(uploads_dir) 
                        if os.path.isdir(os.path.join(uploads_dir, d)) and d != 'task_info']
            
            if not task_dirs:
                raise Exception("没有找到任何任务数据")
            
            export_task['status'] = 'processing'
            export_task['message'] = f'正在处理 {len(task_dirs)} 个任务...'
            
            total_files = 0
            
            # 处理每个任务目录
            for i, task_dir in enumerate(task_dirs):
                task_path = os.path.join(uploads_dir, task_dir)
                
                # 解析任务ID和episode ID
                task_id, episode_id = self._parse_task_info(task_dir)
                
                # 创建目标目录结构
                self._create_target_structure(export_path, task_id, episode_id)
                
                # 复制文件
                files_copied = self._copy_task_files(task_path, export_path, task_id, episode_id)
                total_files += files_copied
                
                # 更新进度
                progress = int((i + 1) / len(task_dirs) * 100)
                export_task['progress'] = progress
                export_task['message'] = f'已处理 {i + 1}/{len(task_dirs)} 个任务'
            
            # 创建task_catalog.json
            self._create_task_catalog(export_path, task_dirs)

            # 生成 task_info JSON（模仿客户端导出结构）
            try:
                task_info_count = self._export_task_info_json(export_path)
            except Exception as e:
                task_info_count = 0
                print(f"导出 task_info 失败: {e}")
            
            # 完成导出
            export_task['status'] = 'completed'
            export_task['progress'] = 100
            export_task['message'] = f'导出完成，共处理 {total_files} 个文件；task_info: {task_info_count} 个'
            export_task['file_count'] = total_files
            export_task['completed_at'] = datetime.now()
            
        except Exception as e:
            export_task['status'] = 'failed'
            export_task['error_message'] = str(e)
            export_task['completed_at'] = datetime.now()
            print(f"导出失败: {e}")
        
        finally:
            self._running_exports -= 1
    
    def _parse_task_info(self, task_dir_name):
        """从目录名解析task_id和episode_id"""
        # 格式: "Take toast from toaster_367_59"
        # 提取最后的数字作为task_id和episode_id
        parts = task_dir_name.split('_')
        if len(parts) >= 2:
            try:
                task_id = parts[-2]
                episode_id = parts[-1]
                return task_id, episode_id
            except (ValueError, IndexError):
                pass
        
        # 如果解析失败，使用默认值
        return "unknown", "unknown"
    
    def _create_target_structure(self, export_path, task_id, episode_id):
        """创建目标目录结构"""
        dirs_to_create = [
            f"task_info",
            f"observations/{task_id}/{episode_id}/videos",
            f"observations/{task_id}/{episode_id}/depth",
            f"parameters/{task_id}/{episode_id}/camera",
            f"skeletonData/{task_id}/{episode_id}",
            f"kinematicData/{task_id}/{episode_id}",
            f"imu/{task_id}/{episode_id}",
            f"tactileFeedback/{task_id}/{episode_id}",
            f"tactile_feedback/{task_id}/{episode_id}"
        ]
        
        for dir_path in dirs_to_create:
            full_path = os.path.join(export_path, dir_path)
            os.makedirs(full_path, exist_ok=True)
    
    def _copy_task_files(self, source_path, export_path, task_id, episode_id):
        """复制任务文件到目标结构"""
        files_copied = 0
        
        # 定义源目录到目标目录的映射
        mappings = {
            'parameters': f'parameters/{task_id}/{episode_id}',
            'skeleton': f'skeletonData/{task_id}/{episode_id}',
            'kinematic': f'kinematicData/{task_id}/{episode_id}',
            'IMU': f'imu/{task_id}/{episode_id}',
            'Tactile': f'tactileFeedback/{task_id}/{episode_id}',
            'tactileFeedback': f'tactileFeedback/{task_id}/{episode_id}',
            'tactile_feedback': f'tactile_feedback/{task_id}/{episode_id}',
            'video': f'observations/{task_id}/{episode_id}/videos'
        }
        
        # 复制各个目录
        for source_dir, target_dir in mappings.items():
            source_full_path = os.path.join(source_path, source_dir)
            if os.path.exists(source_full_path):
                target_full_path = os.path.join(export_path, target_dir)
                files_copied += self._copy_directory(source_full_path, target_full_path)
        
        return files_copied
    
    def _copy_directory(self, source, target):
        """复制目录及其内容"""
        files_copied = 0
        try:
            if os.path.isdir(source):
                shutil.copytree(source, target, dirs_exist_ok=True)
                # 计算复制的文件数量
                for root, dirs, files in os.walk(target):
                    files_copied += len(files)
        except Exception as e:
            print(f"复制目录失败 {source} -> {target}: {e}")
        
        return files_copied
    
    def _create_task_catalog(self, export_path, task_dirs):
        """创建task_catalog.json文件"""
        catalog_path = os.path.join(export_path, 'task_catalog.json')
        try:
            with open(catalog_path, 'w', encoding='utf-8') as f:
                f.write('{}')  # 空JSON对象
        except Exception as e:
            print(f"创建task_catalog.json失败: {e}")

    def _export_task_info_json(self, export_path):
        """将 TaskInfo 按业务 task_id 导出为 JSON 文件到 export_path/task_info 下。
        结构参照客户端 ExportManager._export_task_info_data：
        每个 task_id 一个 JSON 文件，数组元素包含 episode_id、label_info.action_config、task_name、init_scene_text。
        """
        import json

        task_info_dir = os.path.join(export_path, 'task_info')
        os.makedirs(task_info_dir, exist_ok=True)

        # 收集所有 TaskInfo，按 task_id 分组
        all_tasks = list(TaskInfo.objects.all().only('task_id', 'episode_id', 'task_name', 'init_scene_text', 'action_config'))
        task_id_to_items = {}
        for it in all_tasks:
            biz_id = str(it.task_id or '')
            if not biz_id:
                continue
            task_id_to_items.setdefault(biz_id, []).append(it)

        exported_count = 0
        for biz_id, items in task_id_to_items.items():
            export_array = []
            for it in items:
                # episode_id 尽量转为 int，否则保留字符串
                try:
                    ep_val = int(it.episode_id)
                except Exception:
                    ep_val = str(it.episode_id)
                export_array.append({
                    'episode_id': ep_val,
                    'label_info': {'action_config': it.action_config or []},
                    'task_name': it.task_name or '',
                    'init_scene_text': it.init_scene_text or ''
                })

            output_file = os.path.join(task_info_dir, f"{biz_id}.json")
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(export_array, f, ensure_ascii=False, indent=2)
                exported_count += 1
            except Exception as e:
                print(f"写入 task_info 文件失败 {output_file}: {e}")
                continue

        return exported_count
    
    @action(detail=False, methods=['get'])
    def status(self, request):
        """查询导出状态"""
        export_id = request.query_params.get('export_id')
        if not export_id:
            return Response({'error': '缺少export_id参数'}, status=status.HTTP_400_BAD_REQUEST)
        
        if export_id not in self._active_exports:
            return Response({'error': '导出任务不存在'}, status=status.HTTP_404_NOT_FOUND)
        
        task = self._active_exports[export_id]
        return Response({
            'export_id': task['export_id'],
            'status': task['status'],
            'progress': task['progress'],
            'message': task['message'],
            'error_message': task['error_message'],
            'created_at': task['created_at'].isoformat(),
            'completed_at': task['completed_at'].isoformat() if task['completed_at'] else None,
            'export_path': task['export_path'],
            'file_count': task['file_count']
        })
    
    @action(detail=False, methods=['get'], url_path='list')
    def list_exports(self, request):
        """列出所有导出任务"""
        tasks = []
        for task in self._active_exports.values():
            tasks.append({
                'export_id': task['export_id'],
                'status': task['status'],
                'progress': task['progress'],
                'message': task['message'],
                'created_at': task['created_at'].isoformat(),
                'completed_at': task['completed_at'].isoformat() if task['completed_at'] else None,
                'file_count': task['file_count']
            })
        
        return Response({
            'exports': tasks,
            'total': len(tasks),
            'running': self._running_exports,
            'queued': len(self._export_queue)
        })
