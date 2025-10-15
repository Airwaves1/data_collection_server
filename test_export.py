#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试导出API的简单脚本
"""

import requests
import time
import json

def test_export_api():
    """测试导出API"""
    
    base_url = "http://localhost:8000"
    
    print("🚀 开始测试导出API...")
    
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
        
        # 2. 轮询状态
        print("⏳ 等待导出完成...")
        while True:
            status_response = requests.get(f"{base_url}/api/export/status/?export_id={export_id}")
            
            if status_response.status_code == 200:
                status_data = status_response.json()
                status = status_data['status']
                progress = status_data['progress']
                message = status_data['message']
                
                print(f"📊 状态: {status} | 进度: {progress}% | {message}")
                
                if status == 'completed':
                    print(f"🎉 导出完成!")
                    print(f"📁 导出路径: {status_data['export_path']}")
                    print(f"📄 文件数量: {status_data['file_count']}")
                    break
                elif status == 'failed':
                    print(f"❌ 导出失败: {status_data['error_message']}")
                    break
                
                time.sleep(2)  # 等待2秒再查询
            else:
                print(f"❌ 查询状态失败: {status_response.status_code}")
                break
        
        # 3. 列出所有导出任务
        print("\n📋 所有导出任务:")
        list_response = requests.get(f"{base_url}/api/export/list/")
        if list_response.status_code == 200:
            list_data = list_response.json()
            for task in list_data['exports']:
                print(f"  - {task['export_id']}: {task['status']} ({task['progress']}%)")
        
    except Exception as e:
        print(f"❌ 测试异常: {e}")

if __name__ == "__main__":
    test_export_api()
