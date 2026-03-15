"""
混合转换方案测试脚本
"""
import asyncio
import base64
from pathlib import Path

async def test_pdf_parser():
    """测试PDF解析功能"""
    print("=" * 60)
    print("测试1: PDF解析和样式提取")
    print("=" * 60)
    
    try:
        from app.services.pdf_parser import (
            extract_pdf_styles, 
            parse_lesson_content,
            build_html_with_style,
            generate_basic_template
        )
        
        # 测试样式提取（需要实际的PDF文件）
        print("✓ PDF解析模块导入成功")
        
        # 测试教案内容解析
        test_content = """
        # 教案标题
        
        一、教学目标
        培养学生的数学思维能力
        
        二、教学内容
        本节课主要学习旋转对称图形
        """
        
        sections = parse_lesson_content(test_content)
        print(f"✓ 内容解析成功，解析出 {len(sections)} 个章节")
        
        # 测试HTML生成
        from app.services.pdf_parser import get_default_style
        style = get_default_style()
        html = build_html_with_style(style, sections)
        print(f"✓ HTML生成成功，长度: {len(html)} 字符")
        
        # 测试基础模版
        basic_html = generate_basic_template(test_content)
        print(f"✓ 基础模版生成成功，长度: {len(basic_html)} 字符")
        
        print("\n✅ PDF解析功能测试通过\n")
        return True
        
    except Exception as e:
        print(f"\n❌ PDF解析功能测试失败: {e}\n")
        import traceback
        traceback.print_exc()
        return False


async def test_qwen_service():
    """测试Qwen服务"""
    print("=" * 60)
    print("测试2: Qwen服务")
    print("=" * 60)
    
    try:
        from app.services.qwen_service import (
            convert_with_qwen_pdf,
            convert_with_qwen_image,
            convert_with_qwen_base64
        )
        
        print("✓ Qwen服务模块导入成功")
        print("⚠ 实际测试需要配置QWEN_API_KEY")
        print("\n✅ Qwen服务模块测试通过（仅导入测试）\n")
        return True
        
    except Exception as e:
        print(f"\n❌ Qwen服务测试失败: {e}\n")
        import traceback
        traceback.print_exc()
        return False


async def test_converter():
    """测试转换器主逻辑"""
    print("=" * 60)
    print("测试3: 混合转换逻辑")
    print("=" * 60)
    
    try:
        from app.services.converter import (
            convert_lesson,
            parse_and_fill_pdf,
            generate_basic_template,
            convert_to_markdown,
            convert_to_txt,
            convert_to_pdf
        )
        
        print("✓ 转换器模块导入成功")
        
        # 测试基础模版生成
        test_content = "这是测试教案内容"
        basic_html = generate_basic_template(test_content)
        print(f"✓ 基础模版生成成功，长度: {len(basic_html)} 字符")
        
        # 测试格式转换
        test_html = "<html><body><h1>测试</h1><p>内容</p></body></html>"
        
        md = convert_to_markdown(test_html)
        print(f"✓ Markdown转换成功，长度: {len(md)} 字符")
        
        txt = convert_to_txt(test_html)
        print(f"✓ TXT转换成功，长度: {len(txt)} 字符")
        
        print("\n✅ 混合转换逻辑测试通过\n")
        return True
        
    except Exception as e:
        print(f"\n❌ 混合转换逻辑测试失败: {e}\n")
        import traceback
        traceback.print_exc()
        return False


async def test_models():
    """测试数据模型"""
    print("=" * 60)
    print("测试4: 数据模型")
    print("=" * 60)
    
    try:
        from app.models import (
            LessonPlanMetadata,
            LessonPlan,
            ConvertRequest,
            ConvertResponse
        )
        
        print("✓ 数据模型导入成功")
        
        # 测试ConvertRequest
        request = ConvertRequest(
            lesson_plan_id="test-123",
            template_pdf="base64string",
            output_formats=["json", "docx"],
            method="auto"
        )
        print(f"✓ ConvertRequest创建成功，method={request.method}")
        
        # 测试默认值
        request2 = ConvertRequest(
            lesson_plan_id="test-456",
            template_pdf="base64string",
            output_formats=["pdf"]
        )
        print(f"✓ ConvertRequest默认method={request2.method}")
        
        print("\n✅ 数据模型测试通过\n")
        return True
        
    except Exception as e:
        print(f"\n❌ 数据模型测试失败: {e}\n")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print(" 混合PDF格式转换方案 - 功能测试")
    print("=" * 60 + "\n")
    
    results = []
    
    # 运行测试
    results.append(("PDF解析", await test_pdf_parser()))
    results.append(("Qwen服务", await test_qwen_service()))
    results.append(("混合转换", await test_converter()))
    results.append(("数据模型", await test_models()))
    
    # 总结
    print("\n" + "=" * 60)
    print(" 测试总结")
    print("=" * 60)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name}: {status}")
    
    total = len(results)
    passed = sum(1 for _, r in results if r)
    
    print(f"\n总计: {passed}/{total} 项测试通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！系统已准备就绪。")
        print("\n下一步:")
        print("1. 配置.env文件（设置QWEN_API_KEY）")
        print("2. 启动服务: python run.py")
        print("3. 打开format_converter.html进行实际测试")
    else:
        print("\n⚠ 部分测试未通过，请检查错误信息")
    
    print("\n" + "=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
