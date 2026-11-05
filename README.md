# qc-ml-playground

Repo containing mini projects involving ML/AI and Quantum Chemistry
- `projects/<name>/` — one folder per project, each with its own README


## Projects
- [`projects/orca-assistant`](projects/orca-assistant) — RAG chat over the ORCA 6.1.1 manual: PyMuPDF extraction with layout-aware chunking, chromadb + Ollama embeddings, grounded answers with cited sections, Streamlit UI. Retrieval baseline page@5 = 0.90 on 20 hand-written questions.
- [`projects/FrankensteinGPUStarter`](projects/FrankensteinGPUStarter) — QLoRA fine-tuning of Mistral-7B on Colab (warm-up for the assistant's fine-tuning stage).