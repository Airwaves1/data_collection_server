#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试导出API修复
"""

import requests
import time

def test_export_api():
    """测试导出API"""
    
    base_url = "http://localhost:8000"
    
    print("🚀 测试导出API修复...")
    
    try:
        # 1. 启动导出
        print("📤 启动导出任务...")
        response = requests.post(f"{base_url}/api/export/export_all/")
        
        if response.status_code == 200:
            result = response.json()
            export_id = result['export_id']
            print(f"✅ 导出任务已创建: {export_id}")
        else:
            print(f"❌ 创建导出任务失败: {response.status_code}")
            print(f"错误: {response.text}")
            return
        
        # 2. 测试状态查询
        print("🔍 测试状态查询...")
        status_response = requests.get(f"{base_url}/api/export/status/?export_id={export_id}")
        
        if status_response.status_code == 200:
            status_data = status_response.json()
            print(f"✅ 状态查询成功: {status_data['status']}")
        else:
            print(f"❌ 状态查询失败: {status_response.status_code}")
            print(f"错误: {status_response.text}")
            return
        
        # 3. 测试列表查询
        print("📋 测试列表查询...")
        list_response = requests.get(f"{base_url}/api/export/list/")
        
        if list_response.status_code == 200:
            list_data = list_response.json()
            print(f"✅ 列表查询成功: {list_data['total']} 个任务")
        else:
            print(f"❌ 列表查询失败: {list_response.status_code}")
            print(f"错误: {list_response.text}")
        
        print("🎉 所有测试通过！")
        
    except Exception as e:
        print(f"❌ 测试异常: {e}")

if __name__ == "__main__":
    test_export_api()
