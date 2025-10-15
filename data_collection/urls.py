from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# 创建路由器
router = DefaultRouter()
router.register(r'collectors', views.CollectorViewSet)
router.register(r'tasks', views.TaskInfoViewSet)
router.register(r'observations', views.ObservationsViewSet)
router.register(r'parameters', views.ParametersViewSet)
router.register(r'skeleton-data', views.SkeletonDataViewSet)
router.register(r'kinematic-data', views.KinematicDataViewSet)
router.register(r'imu-data', views.IMUDataViewSet)
router.register(r'tactile-feedback', views.TactileFeedbackViewSet)
router.register(r'files', views.FileUploadViewSet, basename='files')

urlpatterns = [
    path('api/', include(router.urls)),
]
