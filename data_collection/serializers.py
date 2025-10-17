from rest_framework import serializers
from .models import (
    Collector, TaskInfo, Observations, Parameters, 
    SkeletonData, KinematicData, IMUData, TactileFeedback, ObjectData
)


class CollectorSerializer(serializers.ModelSerializer):
    """采集者序列化器"""
    class Meta:
        model = Collector
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')
        extra_kwargs = {
            'password': {'write_only': True}  # 密码字段只写不读
        }

class CollectorCreateSerializer(serializers.ModelSerializer):
    """采集者创建序列化器"""
    class Meta:
        model = Collector
        fields = ['username', 'password', 'collector_organization', 'collector_id', 'collector_name', 'target_customer']

class CollectorLoginSerializer(serializers.Serializer):
    """采集者登录序列化器"""
    username = serializers.CharField(max_length=100)
    password = serializers.CharField(max_length=100)


class ObservationsSerializer(serializers.ModelSerializer):
    """观察数据序列化器"""
    class Meta:
        model = Observations
        fields = '__all__'
        read_only_fields = ('created_at',)


class ParametersSerializer(serializers.ModelSerializer):
    """参数数据序列化器"""
    class Meta:
        model = Parameters
        fields = '__all__'
        read_only_fields = ('created_at',)


class SkeletonDataSerializer(serializers.ModelSerializer):
    """骨骼数据序列化器"""
    class Meta:
        model = SkeletonData
        fields = '__all__'
        read_only_fields = ('created_at',)


class KinematicDataSerializer(serializers.ModelSerializer):
    """运动学数据序列化器"""
    class Meta:
        model = KinematicData
        fields = '__all__'
        read_only_fields = ('created_at',)


class IMUDataSerializer(serializers.ModelSerializer):
    """IMU数据序列化器"""
    class Meta:
        model = IMUData
        fields = '__all__'
        read_only_fields = ('created_at',)


class TactileFeedbackSerializer(serializers.ModelSerializer):
    """触觉反馈数据序列化器"""
    class Meta:
        model = TactileFeedback
        fields = '__all__'
        read_only_fields = ('created_at',)


class ObjectDataSerializer(serializers.ModelSerializer):
    """物体模型数据序列化器"""
    class Meta:
        model = ObjectData
        fields = '__all__'
        read_only_fields = ('created_at',)


class TaskInfoSerializer(serializers.ModelSerializer):
    """任务信息序列化器"""
    collector_name = serializers.CharField(source='collector.collector_name', read_only=True)
    collector_id = serializers.CharField(source='collector.collector_id', read_only=True)
    
    # 关联数据序列化器
    observations = ObservationsSerializer(read_only=True)
    parameters = ParametersSerializer(read_only=True)
    skeleton_data = SkeletonDataSerializer(read_only=True)
    kinematic_data = KinematicDataSerializer(read_only=True)
    imu_data = IMUDataSerializer(read_only=True)
    tactile_feedback = TactileFeedbackSerializer(read_only=True)
    object_data = ObjectDataSerializer(read_only=True)
    
    class Meta:
        model = TaskInfo
        fields = '__all__'
        read_only_fields = ('created_at',)


class TaskInfoCreateSerializer(serializers.ModelSerializer):
    """任务信息创建序列化器（不包含关联数据）"""
    class Meta:
        model = TaskInfo
        fields = [
            'collector', 'task_id', 'task_name', 'task_name_cn', 'init_scene_text', 
            'action_config', 'task_status', 'completed_at', 'recording_end_time', 'exported'
        ]


class CollectorCreateUpdateSerializer(serializers.ModelSerializer):
    """采集者创建/更新序列化器"""
    class Meta:
        model = Collector
        fields = [
            'collector_organization', 'collector_id', 'collector_name', 'target_customer'
        ]

    def validate_collector_id(self, value):
        """验证采集者ID唯一性"""
        if self.instance is None:  # 创建时
            if Collector.objects.filter(collector_id=value).exists():
                raise serializers.ValidationError("采集者ID已存在")
        else:  # 更新时
            if Collector.objects.filter(collector_id=value).exclude(pk=self.instance.pk).exists():
                raise serializers.ValidationError("采集者ID已存在")
        return value
