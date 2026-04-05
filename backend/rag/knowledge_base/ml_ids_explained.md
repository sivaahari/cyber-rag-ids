# Machine Learning IDS — How It Works

## LSTM for Network Anomaly Detection
Our system uses a Long Short-Term Memory (LSTM) neural network trained on
the CIC-IDS2018 / NSL-KDD dataset to detect network intrusions.

## Feature Set (NSL-KDD / CIC-IDS2018)
The model analyzes these key network flow features:
- Duration, Protocol Type, Service, Flag
- Source/Destination bytes
- Land, Wrong Fragment, Urgent
- Hot indicators, Failed logins
- Logged In, Num compromised, Root shell
- Num file creations, Num shells, Num access files
- Is Guest Login, Connection count, SRV count
- Error rates (SERROR, RERROR, SAME_SRV_RATE)
- Destination host statistics

## Model Architecture
- Input: Normalized feature vector (41 or 78 features depending on dataset)
- LSTM Layer 1: 128 hidden units, dropout 0.3
- LSTM Layer 2: 64 hidden units, dropout 0.3
- Fully Connected: 32 → 1 (binary classification) or N classes
- Activation: Sigmoid (binary) or Softmax (multiclass)

## Training Details
- Dataset: NSL-KDD (125,973 training samples, 22,544 test samples)
- Attack categories: Normal, DoS, Probe, R2L, U2R
- Class balancing: SMOTE oversampling
- Optimizer: Adam (lr=0.001, weight_decay=1e-5)
- Loss: Binary Cross-Entropy / Focal Loss
- Epochs: 50, Batch size: 256
- Validation: Stratified k-fold (k=5)

## Performance Metrics
- Accuracy: ~98.5% on NSL-KDD test set
- Precision: 0.987, Recall: 0.982, F1: 0.984
- False Positive Rate: < 0.02

## Inference Pipeline
1. Raw network packet/CSV row received
2. Feature extraction (41/78 features)
3. StandardScaler normalization (fitted on training data)
4. LSTM forward pass → probability score [0,1]
5. Threshold: > 0.5 = ANOMALY, else NORMAL
6. Anomaly → sent to RAG advisor for explanation
