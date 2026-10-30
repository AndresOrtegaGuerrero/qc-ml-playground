# Frankenstein QLoRA starter

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/AndresOrtegaGuerrero/qc-ml-playground/blob/main/projects/FrankensteinGPUStarter/FrankensteinQLoRAStarter.ipynb)

Fine-tuning Mistral-7B with QLoRA on the text of *Frankenstein*,
using Hugging Face `transformers`, `peft` and `bitsandbytes`.

The model is loaded in 4-bit, LoRA adapters are trained for ~15 min
on a Colab T4, and perplexity is compared before and after.

Files: `FrankensteinQLoRAStarter.ipynb` (notebook), `frankenstein_chunks.csv` (training text).