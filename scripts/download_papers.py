"""
Download the exact three research papers required by THE RELAY:
1. Attention Is All You Need — arXiv:1706.03762v7
2. Moshi: a speech-text foundation model for real-time dialogue — arXiv:2410.00037v1
3. Dynamic Chunking for End-to-End Hierarchical Sequence Modeling — arXiv:2507.07955v2
"""

import os
import sys
import time
import urllib.request

PAPERS = [
    {
        "id": "1706.03762v7",
        "title": "Attention Is All You Need",
        "url": "https://arxiv.org/pdf/1706.03762v7.pdf",
        "filename": "1706.03762v7_Attention_Is_All_You_Need.pdf"
    },
    {
        "id": "2410.00037v1",
        "title": "Moshi: a speech-text foundation model for real-time dialogue",
        "url": "https://arxiv.org/pdf/2410.00037v1.pdf",
        "filename": "2410.00037v1_Moshi_Speech_Text_Foundation_Model.pdf"
    },
    {
        "id": "2507.07955v2",
        "title": "Dynamic Chunking for End-to-End Hierarchical Sequence Modeling",
        "url": "https://arxiv.org/pdf/2507.07955v2.pdf",
        "filename": "2507.07955v2_Dynamic_Chunking_Hierarchical_Sequence_Modeling.pdf"
    }
]

def download_papers(target_dir: str = "data/papers"):
    os.makedirs(target_dir, exist_ok=True)
    headers = {"User-Agent": "TheRelayResearchAssistant/1.0 (academic-benchmarking; contact: researcher@example.com)"}

    for paper in PAPERS:
        dest_path = os.path.join(target_dir, paper["filename"])
        if os.path.exists(dest_path) and os.path.getsize(dest_path) > 10000:
            print(f"[EXISTS] {paper['id']} already exists at {dest_path} ({os.path.getsize(dest_path)} bytes)")
            continue

        print(f"[DOWNLOADING] {paper['id']} from {paper['url']}...")
        req = urllib.request.Request(paper["url"], headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp, open(dest_path, "wb") as f:
                f.write(resp.read())
            size = os.path.getsize(dest_path)
            print(f"[SUCCESS] Saved {paper['filename']} ({size} bytes)")
        except Exception as e:
            print(f"[ERROR] Failed to download {paper['id']}: {e}")
            raise e
        time.sleep(1)  # Respectful arXiv rate limiting

if __name__ == "__main__":
    download_papers()

