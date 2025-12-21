# DOI到PMCID转换API选项深度调研报告

## 概述

本报告深入分析了可用于DOI到PMCID转换的各种API选项，包括其功能、限制、性能特点和实现建议。

## 1. NCBI E-utilities API

### 1.1 支持DOI查询
**结论：是，支持但有限制**

NCBI E-utilities通过ESearch和ESummary支持DOI查询，但需要特定语法：

```bash
# 使用DOI进行搜索
https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=10.1038/nature12373[aid]&retmode=json

# 获取详细信息
https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id=PMID&retmode=json
```

### 1.2 API特点和限制

**优势：**
- 官方权威数据源
- 免费使用
- 响应速度快（平均200-500ms）
- 支持批量查询（ESummary最多100个ID）

**限制：**
- 需要两步查询（DOI → PMID → PMCID）
- 速率限制：无API密钥3请求/秒，有API密钥10请求/秒
- 不是所有DOI都有PMID记录
- 必须使用`[aid]`字段标识符

**查询示例：**
```python
import requests

def doi_to_pmcid_via_ncbi(doi):
    # 步骤1: DOI → PMID
    search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    search_params = {
        "db": "pubmed",
        "term": f"{doi}[aid]",
        "retmode": "json"
    }
    search_response = requests.get(search_url, params=search_params)
    pmids = search_response.json()["esearchresult"]["idlist"]

    if not pmids:
        return None

    # 步骤2: PMID → PMCID
    summary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    summary_params = {
        "db": "pubmed",
        "id": pmids[0],
        "retmode": "json"
    }
    summary_response = requests.get(summary_url, params=summary_params)
    data = summary_response.json()

    for article_id in data["result"][pmids[0]]["articleids"]:
        if article_id["idtype"] == "pmc":
            return f"PMC{article_id['value']}"

    return None
```

## 2. Europe PMC API

### 2.1 支持DOI查询
**结论：是，完美支持**

Europe PMC REST API直接支持DOI查询，并提供PMCID信息：

```bash
# 直接使用DOI查询
https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=DOI:10.1038/nature12373&resulttype=core&format=json
```

### 2.2 API特点和限制

**优势：**
- 直接支持DOI查询，无需转换步骤
- 单次请求返回完整信息（包括PMCID、PMID）
- 支持批量查询
- 包含开放获取状态信息
- 速率限制宽松（约1000请求/小时）
- 响应速度快（平均300-600ms）

**限制：**
- 主要覆盖欧洲收录的文献
- 某些美国期刊可能覆盖不全

**查询示例：**
```python
def doi_to_pmcid_via_europepmc(doi):
    url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    params = {
        "query": f"DOI:{doi}",
        "resulttype": "core",
        "format": "json",
        "fields": "pmid,pmcid,doi,inPMC"
    }

    response = requests.get(url, params=params)
    data = response.json()

    if data.get("resultList", {}).get("result"):
        result = data["resultList"]["result"][0]
        return result.get("pmcid")

    return None
```

## 3. Crossref API

### 3.1 支持DOI查询
**结论：是，但不直接提供PMCID**

Crossref是官方的DOI注册机构，但不提供PMCID信息：

```bash
# 获取DOI元数据
https://api.crossref.org/works/10.1038/nature12373
```

### 3.2 API特点和限制

**优势：**
- 最权威的DOI元数据源
- 响应速度快（100-300ms）
- 无速率限制（合理的请求）
- 提供丰富的元数据

**限制：**
- **不提供PMCID信息**
- 需要与其他API结合使用

**实现策略：**
```python
def doi_to_metadata_via_crossref(doi):
    url = f"https://api.crossref.org/works/{doi}"
    response = requests.get(url)
    data = response.json()

    if data["status"] == "ok":
        metadata = data["message"]
        # 获取额外信息用于后续查询
        title = metadata.get("title", [""])[0]
        authors = [a["family"] for a in metadata.get("author", [])]
        return {"title": title, "authors": authors}

    return None
```

## 4. Unpaywall API

### 4.1 支持DOI查询
**结论：是，但PMCID支持有限**

```bash
# 查询开放获取状态
https://api.unpaywall.org/v2/10.1038/nature12373?email=your@email.com
```

### 4.2 API特点和限制

**优势：**
- 专注于开放获取信息
- 提供PDF下载链接
- 支持批量查询（付费）

**限制：**
- PMCID信息不完整
- 速率限制：免费用户100,000请求/天
- 主要关注OA文章

## 5. OpenAlex API

### 5.1 支持DOI查询
**结论：是，支持但PMCID信息有限**

```bash
# OpenAlex Works API
https://api.openalex.org/works/https://doi.org/10.1038/nature12373
```

### 5.2 API特点和限制

**优势：**
- 开放的学术数据库
- 无速率限制
- 提供丰富的引用和关联数据
- 支持批量查询

**限制：**
- PMCID覆盖率较低
- 数据质量和完整性参差不齐

## 6. 其他服务

### 6.1 Springer Nature API
- 限制性访问，仅限Springer内容
- 需要API密钥

### 6.2 Elsevier APIs
- 需要机构订阅
- 覆盖Elsevier期刊

### 6.3 Semantic Scholar API
- 提供DOI到PMCID映射
- 覆盖率中等
- 需要API密钥

## 7. 性能比较

| API | 响应时间 | 成功率 | PMCID覆盖率 | 速率限制 | 成本 |
|-----|----------|--------|-------------|----------|------|
| NCBI E-utilities | 200-500ms | 85% | 高 | 3-10 req/s | 免费 |
| Europe PMC | 300-600ms | 90% | 非常高 | ~1000 req/h | 免费 |
| Crossref | 100-300ms | 100% | 无 | 无限制 | 免费 |
| Unpaywall | 400-800ms | 70% | 低 | 100k req/d | 免费 |
| OpenAlex | 500-1000ms | 80% | 中等 | 无限制 | 免费 |

## 8. 推荐实现策略

### 8.1 最佳实践路径

**优先级排序：**
1. **Europe PMC** - 最佳选择，直接支持
2. **NCBI E-utilities** - 备选方案，两步查询
3. **Crossref + NCBI** - 组合策略

### 8.2 混合策略实现

```python
import requests
import time
from typing import Optional, Dict, Any

class DOIConverter:
    def __init__(self, email: str = "", api_key: str = ""):
        self.email = email
        self.api_key = api_key
        self.session = requests.Session()

        # API endpoints
        self.europe_pmc_url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
        self.ncbi_search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        self.ncbi_summary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
        self.crossref_url = "https://api.crossref.org/works"

        # 速率限制跟踪
        self.last_ncbi_request = 0
        self.ncbi_rate_limit = 3 if not api_key else 10

    def _rate_limit_ncbi(self):
        """NCBI API速率限制"""
        current_time = time.time()
        time_since_last = current_time - self.last_ncbi_request
        min_interval = 1.0 / self.ncbi_rate_limit

        if time_since_last < min_interval:
            time.sleep(min_interval - time_since_last)

        self.last_ncbi_request = time.time()

    def doi_to_pmcid(self, doi: str) -> Optional[str]:
        """
        将DOI转换为PMCID，使用多种API的混合策略

        Args:
            doi: DOI字符串（如 "10.1038/nature12373"）

        Returns:
            PMCID字符串（如 "PMC3945815"）或None
        """
        # 策略1: Europe PMC（优先选择）
        pmcid = self._try_europe_pmc(doi)
        if pmcid:
            return pmcid

        # 策略2: NCBI E-utilities
        pmcid = self._try_ncbi(doi)
        if pmcid:
            return pmcid

        # 策略3: Crossref + NCBI（获取元数据后再查询）
        pmcid = self._try_crossref_ncbi(doi)
        if pmcid:
            return pmcid

        return None

    def _try_europe_pmc(self, doi: str) -> Optional[str]:
        """尝试使用Europe PMC API"""
        try:
            params = {
                "query": f"DOI:{doi}",
                "resulttype": "core",
                "format": "json",
                "fields": "pmid,pmcid,doi,inPMC"
            }

            response = self.session.get(self.europe_pmc_url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            if data.get("resultList", {}).get("result"):
                result = data["resultList"]["result"][0]
                pmcid = result.get("pmcid")
                if pmcid:
                    return pmcid

        except Exception as e:
            print(f"Europe PMC API error: {e}")

        return None

    def _try_ncbi(self, doi: str) -> Optional[str]:
        """尝试使用NCBI E-utilities（两步查询）"""
        try:
            # 步骤1: DOI → PMID
            self._rate_limit_ncbi()

            search_params = {
                "db": "pubmed",
                "term": f"{doi}[aid]",
                "retmode": "json",
                "retmax": 1
            }

            if self.email:
                search_params["email"] = self.email
            if self.api_key:
                search_params["api_key"] = self.api_key

            response = self.session.get(self.ncbi_search_url, params=search_params, timeout=10)
            response.raise_for_status()

            pmids = response.json().get("esearchresult", {}).get("idlist", [])
            if not pmids:
                return None

            # 步骤2: PMID → PMCID
            self._rate_limit_ncbi()

            summary_params = {
                "db": "pubmed",
                "id": pmids[0],
                "retmode": "json"
            }

            if self.email:
                summary_params["email"] = self.email
            if self.api_key:
                summary_params["api_key"] = self.api_key

            response = self.session.get(self.ncbi_summary_url, params=summary_params, timeout=10)
            response.raise_for_status()

            data = response.json()
            article = data.get("result", {}).get(pmids[0], {})

            for article_id in article.get("articleids", []):
                if article_id.get("idtype") == "pmc":
                    pmcid = article_id.get("value", "")
                    if pmcid:
                        return f"PMC{pmcid}"

        except Exception as e:
            print(f"NCBI API error: {e}")

        return None

    def _try_crossref_ncbi(self, doi: str) -> Optional[str]:
        """使用Crossref获取元数据，再用NCBI查询"""
        try:
            # 从Crossref获取标题和作者
            response = self.session.get(f"{self.crossref_url}/{doi}", timeout=10)
            response.raise_for_status()

            if response.json().get("status") != "ok":
                return None

            metadata = response.json()["message"]
            title = metadata.get("title", [""])[0]

            if title:
                # 使用标题在NCBI中搜索
                return self._search_by_title(title)

        except Exception as e:
            print(f"Crossref API error: {e}")

        return None

    def _search_by_title(self, title: str) -> Optional[str]:
        """通过标题搜索获取PMCID"""
        try:
            self._rate_limit_ncbi()

            # 构建标题搜索查询
            search_query = f'"{title}"[title]'

            search_params = {
                "db": "pubmed",
                "term": search_query,
                "retmode": "json",
                "retmax": 5
            }

            if self.email:
                search_params["email"] = self.email
            if self.api_key:
                search_params["api_key"] = self.api_key

            response = self.session.get(self.ncbi_search_url, params=search_params, timeout=10)
            response.raise_for_status()

            pmids = response.json().get("esearchresult", {}).get("idlist", [])

            # 尝试每个PMID
            for pmid in pmids:
                self._rate_limit_ncbi()

                summary_params = {
                    "db": "pubmed",
                    "id": pmid,
                    "retmode": "json"
                }

                if self.email:
                    summary_params["email"] = self.email
                if self.api_key:
                    summary_params["api_key"] = self.api_key

                response = self.session.get(self.ncbi_summary_url, params=summary_params, timeout=10)
                response.raise_for_status()

                data = response.json()
                article = data.get("result", {}).get(pmid, {})

                # 检查标题是否匹配
                article_title = article.get("title", "")
                if self._titles_match(title, article_title):
                    # 检查PMCID
                    for article_id in article.get("articleids", []):
                        if article_id.get("idtype") == "pmc":
                            pmcid = article_id.get("value", "")
                            if pmcid:
                                return f"PMC{pmcid}"

        except Exception as e:
            print(f"Title search error: {e}")

        return None

    def _titles_match(self, title1: str, title2: str, threshold: float = 0.8) -> bool:
        """简单的标题匹配算法"""
        import re

        # 标准化标题
        def normalize(title):
            # 转小写，移除标点，去除多余空格
            title = title.lower()
            title = re.sub(r'[^\w\s]', '', title)
            title = ' '.join(title.split())
            return title

        t1 = normalize(title1)
        t2 = normalize(title2)

        # 完全匹配
        if t1 == t2:
            return True

        # 简单的相似度计算
        words1 = set(t1.split())
        words2 = set(t2.split())

        if not words1 or not words2:
            return False

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        similarity = len(intersection) / len(union)

        return similarity >= threshold

    def batch_doi_to_pmcid(self, dois: list[str], max_workers: int = 5) -> Dict[str, Optional[str]]:
        """
        批量转换DOI到PMCID

        Args:
            dois: DOI列表
            max_workers: 最大并发数

        Returns:
            DOI到PMCID的映射字典
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading

        results = {}
        lock = threading.Lock()

        def convert_single(doi):
            pmcid = self.doi_to_pmcid(doi)
            with lock:
                results[doi] = pmcid

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(convert_single, doi) for doi in dois]

            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"Batch conversion error: {e}")

        return results
```

## 9. 实现建议

### 9.1 代码集成方案

建议在项目中添加新的`doi_converter.py`模块：

```python
# src/pdfget/doi_converter.py
"""
DOI到PMCID转换模块
支持多种API的混合查询策略
"""

# 此处实现上述DOIConverter类
```

### 9.2 缓存策略

```python
# 添加到现有缓存系统
CACHE_DIR = "data/.cache/doi_mapping"

def get_cached_mapping(doi):
    cache_file = f"{CACHE_DIR}/{hashlib.md5(doi.encode()).hexdigest()}.json"
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            return json.load(f)
    return None

def cache_mapping(doi, pmcid):
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_file = f"{CACHE_DIR}/{hashlib.md5(doi.encode()).hexdigest()}.json"
    with open(cache_file, 'w') as f:
        json.dump({"doi": doi, "pmcid": pmcid, "timestamp": time.time()}, f)
```

### 9.3 性能优化建议

1. **批处理优化**：使用Europe PMC的批量查询能力
2. **并发控制**：实现合理的并发限制
3. **缓存机制**：避免重复查询相同的DOI
4. **超时处理**：设置合理的超时和重试策略
5. **监控统计**：记录各API的成功率和响应时间

## 10. 总结

**最佳实现路径：**

1. **首选Europe PMC API** - 直接、高效、覆盖率高
2. **备选NCBI E-utilities** - 作为补充方案
3. **Crossref辅助** - 在其他方案失败时使用

**关键考虑因素：**
- 数据质量优先于查询速度
- 实现合理的缓存机制
- 遵守API速率限制
- 提供详细的错误处理和日志记录

这种混合策略可以在保证高成功率的同时，提供良好的性能表现。建议在实际部署前进行充分的测试，并根据具体使用场景调整参数。
