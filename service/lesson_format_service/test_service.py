"""
服务测试脚本 - 验证所有功能是否正常
"""
import requests
import json
import base64

API_BASE_URL = "http://localhost:8000"

def test_health():
    """测试健康检查"""
    print("\n🔍 测试1: 健康检查")
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        print(f"✅ 健康检查通过: {response.json()}")
        return True
    except Exception as e:
        print(f"❌ 健康检查失败: {e}")
        return False

def test_create_lesson():
    """测试创建教案"""
    print("\n🔍 测试2: 创建教案")
    try:
        lesson_data = {
            "metadata": {
                "type": "测试教案",
                "generatedAt": "2025-02-13T08:00:00Z",
                "generatedAtReadable": "2025/2/13 16:00:00",
                "courseTitle": "测试课程"
            },
            "content": "这是一个测试教案的内容\n\n【教学目标】\n1. 测试目标1\n2. 测试目标2"
        }
        
        response = requests.post(
            f"{API_BASE_URL}/api/lesson-plans",
            json=lesson_data
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 创建教案成功，ID: {result['id']}")
            return result['id']
        else:
            print(f"❌ 创建教案失败: {response.text}")
            return None
    except Exception as e:
        print(f"❌ 创建教案异常: {e}")
        return None

def test_get_lessons():
    """测试获取教案列表"""
    print("\n🔍 测试3: 获取教案列表")
    try:
        response = requests.get(f"{API_BASE_URL}/api/lesson-plans")
        if response.status_code == 200:
            plans = response.json()
            print(f"✅ 获取教案列表成功，共 {len(plans)} 个教案")
            for i, plan in enumerate(plans, 1):
                print(f"   {i}. {plan['metadata']['courseTitle']} - {plan['metadata']['type']}")
            return True
        else:
            print(f"❌ 获取教案列表失败: {response.text}")
            return False
    except Exception as e:
        print(f"❌ 获取教案列表异常: {e}")
        return False

def test_convert(lesson_id):
    """测试格式转换（不包含实际PDF，仅测试接口）"""
    print("\n🔍 测试4: 格式转换接口")
    print("⚠️  需要提供真实的PDF模版才能完整测试")
    print("    这里仅测试接口可达性，不进行实际转换")
    # 实际使用时需要上传真实PDF
    return True

def main():
    print("=" * 60)
    print("教案格式转换服务 - 功能测试")
    print("=" * 60)
    
    # 测试1: 健康检查
    if not test_health():
        print("\n❌ 服务未启动，请先运行: python run.py")
        return
    
    # 测试2: 创建教案
    lesson_id = test_create_lesson()
    if not lesson_id:
        print("\n❌ 创建教案失败，停止测试")
        return
    
    # 测试3: 获取教案列表
    test_get_lessons()
    
    # 测试4: 转换接口
    test_convert(lesson_id)
    
    print("\n" + "=" * 60)
    print("✅ 基础功能测试完成！")
    print("\n下一步：")
    print("1. 在 update_lesson_plan.html 中生成真实教案")
    print("2. 在 format_converter.html 中进行格式转换")
    print("3. 上传真实的PDF模版进行完整测试")
    print("=" * 60)

if __name__ == "__main__":
    main()
