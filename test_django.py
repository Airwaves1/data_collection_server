#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Django服务器测试脚本
"""

import os
import sys
import django
from django.conf import settings
from django.core.management import execute_from_command_line

def test_django_startup():
    """测试Django启动"""
    print("测试Django服务器启动...")
    
    # 设置Django设置模块
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'data_collection_server.settings')
    
    try:
        # 初始化Django
        django.setup()
        print("✅ Django初始化成功")
        
        # 检查URL配置
        from django.urls import reverse
        from django.test import Client
        
        client = Client()
        
        # 测试文件上传API端点
        try:
            response = client.get('/api/files/info/')
            print(f"✅ 文件上传API端点可访问: {response.status_code}")
        except Exception as e:
            print(f"❌ 文件上传API端点测试失败: {e}")
        
        # 测试其他API端点
        try:
            response = client.get('/api/collectors/')
            print(f"✅ 采集者API端点可访问: {response.status_code}")
        except Exception as e:
            print(f"❌ 采集者API端点测试失败: {e}")
        
        print("✅ Django服务器测试通过")
        return True
        
    except Exception as e:
        print(f"❌ Django启动失败: {e}")
        return False

if __name__ == "__main__":
    success = test_django_startup()
    if success:
        print("\n🎉 Django服务器配置正确，可以启动服务")
        print("运行命令: python manage.py runserver")
    else:
        print("\n❌ Django服务器配置有问题，请检查错误信息")
        sys.exit(1)
