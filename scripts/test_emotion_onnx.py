import cv2
import numpy as np

model_path = "/files/emotion-ferplus-8.onnx"
print("Loading model:", model_path)
net = cv2.dnn.readNetFromONNX(model_path)
print("Model loaded successfully into cv2.dnn!")

# emotion-ferplus takes 1x1x64x64 grayscale image
# Classes: neutral, happiness, surprise, sadness, anger, disgust, fear, contempt
EMOTIONS = ["neutral", "happiness", "surprise", "sadness", "anger", "disgust", "fear", "contempt"]

dummy_input = np.zeros((1, 1, 64, 64), dtype=np.float32)
net.setInput(dummy_input)
out = net.forward()
print("Output shape:", out.shape)
print("Output values:", out)
probs = np.exp(out) / np.sum(np.exp(out))
print("Softmax probabilities:", {EMOTIONS[i]: float(probs[0][i]) for i in range(len(EMOTIONS))})
