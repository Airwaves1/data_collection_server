from django.db import models
from django.contrib.auth.models import User
import json


class Collector(models.Model):
    """采集者模型"""
    # 用户认证字段
    username = models.CharField(max_length=100, unique=True, verbose_name="用户名", default="")
    password = models.CharField(max_length=100, verbose_name="密码", default="")  # 明文存储
    
    # 原有字段
    collector_organization = models.CharField(max_length=200, verbose_name="采集者组织")
    collector_id = models.CharField(max_length=100, unique=True, verbose_name="采集者ID")
    collector_name = models.CharField(max_length=100, verbose_name="采集者姓名")
    target_customer = models.CharField(max_length=200, blank=True, null=True, verbose_name="目标客户")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "采集者"
        verbose_name_plural = "采集者"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.collector_name}({self.collector_id})"


class TaskInfo(models.Model):
    """任务信息模型 - 核心元数据"""
    
    # 任务状态选择
    STATUS_CHOICES = [
        ('pending', '待审核'),
        ('accepted', '已接受'),
        ('rejected', '已拒绝'),
        ('ng', 'NG'),
    ]
    
    collector = models.ForeignKey(Collector, on_delete=models.CASCADE, verbose_name="采集者")
    # 业务侧任务ID（非数据库自增ID），用于与外部任务表对齐
    task_id = models.CharField(max_length=100, verbose_name="任务ID", default="", blank=True, db_index=True)
    episode_id = models.CharField(max_length=100, unique=True, verbose_name="Episode ID")
    task_name = models.CharField(max_length=200, verbose_name="任务名称")
    init_scene_text = models.TextField(blank=True, null=True, verbose_name="初始场景文本")
    action_config = models.JSONField(default=list, verbose_name="动作配置")
    task_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="任务状态")
    
    # 外键关联 - 后续由各子模块写入后回填更新
    observations_id = models.IntegerField(null=True, blank=True, verbose_name="观察数据ID")
    parameters_id = models.IntegerField(null=True, blank=True, verbose_name="参数数据ID")
    skeletonData_id = models.IntegerField(null=True, blank=True, verbose_name="骨骼数据ID")
    kinematicData_id = models.IntegerField(null=True, blank=True, verbose_name="运动学数据ID")
    imu_id = models.IntegerField(null=True, blank=True, verbose_name="IMU数据ID")
    tactile_feedback_id = models.IntegerField(null=True, blank=True, verbose_name="触觉反馈数据ID")
    objectData_id = models.IntegerField(null=True, blank=True, verbose_name="物体模型数据ID")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="完成时间")

    class Meta:
        verbose_name = "任务信息"
        verbose_name_plural = "任务信息"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.task_name}({self.episode_id})"


class Observations(models.Model):
    """观察数据模型"""
    task_info = models.ForeignKey(TaskInfo, on_delete=models.CASCADE, verbose_name="任务信息")
    episode_id = models.CharField(max_length=100, verbose_name="Episode ID")
    video_path = models.CharField(max_length=500, verbose_name="视频路径")
    depth_path = models.CharField(max_length=500, blank=True, null=True, verbose_name="深度图路径")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "观察数据"
        verbose_name_plural = "观察数据"
        ordering = ['-created_at']  # 按创建时间倒序排列

    def __str__(self):
        return f"Observations for {self.episode_id}"


class Parameters(models.Model):
    """参数数据模型"""
    task_info = models.ForeignKey(TaskInfo, on_delete=models.CASCADE, verbose_name="任务信息")
    episode_id = models.CharField(max_length=100, verbose_name="Episode ID")
    parameters_path = models.CharField(max_length=500, verbose_name="参数文件路径")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "参数数据"
        verbose_name_plural = "参数数据"

    def __str__(self):
        return f"Parameters for {self.episode_id}"


class SkeletonData(models.Model):
    """骨骼数据模型"""
    task_info = models.ForeignKey(TaskInfo, on_delete=models.CASCADE, verbose_name="任务信息")
    episode_id = models.CharField(max_length=100, verbose_name="Episode ID")
    fbx_path = models.CharField(max_length=500, verbose_name="FBX文件路径")
    bvh_path = models.CharField(max_length=500, verbose_name="BVH文件路径")
    csv_path = models.CharField(max_length=500, verbose_name="CSV文件路径")
    npy_path = models.CharField(max_length=500, verbose_name="NPY文件路径")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "骨骼数据"
        verbose_name_plural = "骨骼数据"

    def __str__(self):
        return f"SkeletonData for {self.episode_id}"


class KinematicData(models.Model):
    """运动学数据模型"""
    task_info = models.ForeignKey(TaskInfo, on_delete=models.CASCADE, verbose_name="任务信息")
    episode_id = models.CharField(max_length=100, verbose_name="Episode ID")
    path = models.CharField(max_length=500, verbose_name="数据文件路径")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "运动学数据"
        verbose_name_plural = "运动学数据"

    def __str__(self):
        return f"KinematicData for {self.episode_id}"


class IMUData(models.Model):
    """IMU数据模型"""
    task_info = models.ForeignKey(TaskInfo, on_delete=models.CASCADE, verbose_name="任务信息")
    episode_id = models.CharField(max_length=100, verbose_name="Episode ID")
    leftHandIMU_path = models.CharField(max_length=500, verbose_name="左手IMU路径")
    rightHandIMU_path = models.CharField(max_length=500, verbose_name="右手IMU路径")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "IMU数据"
        verbose_name_plural = "IMU数据"

    def __str__(self):
        return f"IMUData for {self.episode_id}"


class TactileFeedback(models.Model):
    """触觉反馈数据模型"""
    task_info = models.ForeignKey(TaskInfo, on_delete=models.CASCADE, verbose_name="任务信息")
    episode_id = models.CharField(max_length=100, verbose_name="Episode ID")
    leftHandTac_path = models.CharField(max_length=500, verbose_name="左手触觉路径")
    rightHandTac_path = models.CharField(max_length=500, verbose_name="右手触觉路径")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "触觉反馈数据"
        verbose_name_plural = "触觉反馈数据"

    def __str__(self):
        return f"TactileFeedback for {self.episode_id}"


class ObjectData(models.Model):
    """物体模型数据：object/{task_id}/{episode_id}/ 下的 .fbx/.cmb 等"""
    task_info = models.ForeignKey(TaskInfo, on_delete=models.CASCADE, verbose_name="任务信息")
    episode_id = models.CharField(max_length=100, verbose_name="Episode ID")
    fbx_path = models.CharField(max_length=500, verbose_name="FBX文件路径", blank=True, default="")
    cmb_path = models.CharField(max_length=500, verbose_name="CMB文件路径", blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "物体模型数据"
        verbose_name_plural = "物体模型数据"

    def __str__(self):
        return f"ObjectData for {self.episode_id}"
