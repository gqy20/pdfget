"""
测试摘要补充功能 - 简化版 TDD
"""

import xml.etree.ElementTree as ET


# 我们将要实现的功能
def extract_abstract_from_xml(xml_content):
    """
    从 XML 内容中提取摘要
    这是我们要实现的核心功能
    """
    root = ET.fromstring(xml_content)
    abstract_elem = root.find(".//abstract")
    if abstract_elem is not None:
        # 获取所有文本
        text_content = []
        for elem in abstract_elem.iter():
            if elem.text:
                text_content.append(elem.text)
            if elem.tail:
                text_content.append(elem.tail)
        return " ".join(text_content).strip()
    return None


class TestAbstractExtraction:
    """测试摘要提取功能"""

    def test_simple_abstract_extraction(self):
        """测试：简单摘要提取"""
        xml_content = """
        <article>
            <abstract>
                <p>This is a simple abstract.</p>
            </abstract>
        </article>
        """
        result = extract_abstract_from_xml(xml_content)
        assert result == "This is a simple abstract."

    def test_no_abstract_tag(self):
        """测试：无摘要标签"""
        xml_content = """
        <article>
            <title>Article Title</title>
        </article>
        """
        result = extract_abstract_from_xml(xml_content)
        assert result is None

    def test_nested_abstract(self):
        """测试：嵌套的摘要结构"""
        xml_content = """
        <article>
            <abstract>
                <sec>
                    <title>Background</title>
                    <p>Background text.</p>
                </sec>
                <sec>
                    <title>Conclusion</title>
                    <p>Conclusion text.</p>
                </sec>
            </abstract>
        </article>
        """
        result = extract_abstract_from_xml(xml_content)
        assert "Background text" in result
        assert "Conclusion text" in result

    def test_whitespace_cleaning(self):
        """测试：空白字符清理"""
        xml_content = """
        <article>
            <abstract>
                <p>
                    Text with    extra
                    spaces.
                </p>
            </abstract>
        </article>
        """
        result = extract_abstract_from_xml(xml_content)
        assert "  " not in result
        assert result.startswith("Text with")

    def test_mixed_content(self):
        """测试：混合内容（文本和标签）"""
        xml_content = """
        <article>
            <abstract>
                <p>Text with <bold>bold</bold> and <italic>italic</italic> text.</p>
            </abstract>
        </article>
        """
        result = extract_abstract_from_xml(xml_content)
        assert "Text with" in result
        assert "bold" in result
        assert "italic" in result
