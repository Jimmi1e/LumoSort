import os
import sys
import shutil
from PIL import Image
import torch
import clip.simple_tokenizer as st

if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(__file__)

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

st.BPE_PATH = resource_path("clip_vocab/bpe_simple_vocab_16e6.txt.gz")

from clip import clip
from labels import CLIP_LABELS, LABEL_DISPLAY

# 全局变量
clip_model = None
preprocess_clip = None
text_tokens = None

def initialize_model(status_callback=None):
    """初始化模型，返回是否成功"""
    global clip_model, preprocess_clip, text_tokens
    
    try:
        if status_callback:
            status_callback("Summoning the CLIP model...")
            
        clip_model, preprocess_clip = clip.load("ViT-B/32", device="cpu", download_root=os.path.join(base_path, "models"))
        
        if status_callback:
            status_callback("Preparing the magic labels...")
            
        text_tokens = clip.tokenize(CLIP_LABELS).to("cpu")
        
        if status_callback:
            status_callback("The magic is ready!")
            
        return True
    except Exception as e:
        if status_callback:
            status_callback(f"Error: {str(e)}")
        return False

# Image classification using CLIP
def classify_images_by_clip(paths, output_dir, progress_callback=None):
    global clip_model, preprocess_clip, text_tokens
    
    if clip_model is None or preprocess_clip is None or text_tokens is None:
        raise RuntimeError("模型未初始化，请先调用initialize_model()")
        
    os.makedirs(output_dir, exist_ok=True)
    results = {}
    low_conf_log = []

    for idx, path in enumerate(paths):
        try:
            image = preprocess_clip(Image.open(path).convert("RGB")).unsqueeze(0)
            with torch.no_grad():
                image_features = clip_model.encode_image(image)
                text_features = clip_model.encode_text(text_tokens)
                logits = image_features @ text_features.T
                probs = logits.softmax(dim=-1).cpu().numpy()[0]
                best_idx = int(probs.argmax())
                best_score = probs[best_idx]
                label = CLIP_LABELS[best_idx]
                display_name = LABEL_DISPLAY.get(label, label)

                dest_dir = os.path.join(output_dir, display_name)
                os.makedirs(dest_dir, exist_ok=True)

                filename = os.path.basename(path)
                if best_score < 0.4:
                    low_conf_log.append(f"{filename}\t{display_name}\t{best_score:.3f}")

                shutil.copy(path, os.path.join(dest_dir, filename))

        except Exception as e:
            print(f"Skipped {path}: {e}")

        if progress_callback:
            progress_callback(int((idx + 1) / len(paths) * 100))

    if low_conf_log:
        with open(os.path.join(output_dir, "low_confidence.txt"), "w", encoding="utf-8") as f:
            f.write("File Name\tCategory\tConfidence\n")
            f.write("\n".join(low_conf_log))
    return results
