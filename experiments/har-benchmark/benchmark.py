"""Honest benchmark: is nearest-shape (our Form-native classifier) actually learning?
Compares our quantized-feature 1-NN against small parametric models + SOTA on UCI-HAR.
"""
import time, numpy as np
from sklearn.neighbors import KNeighborsClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.neural_network import MLPClassifier
from sklearn.svm import LinearSVC
from sklearn.metrics import accuracy_score

BASE = "/tmp/ucihar/UCI HAR Dataset"
Xtr = np.loadtxt(f"{BASE}/train/X_train.txt"); ytr = np.loadtxt(f"{BASE}/train/y_train.txt").astype(int)
Xte = np.loadtxt(f"{BASE}/test/X_test.txt");  yte = np.loadtxt(f"{BASE}/test/y_test.txt").astype(int)
print(f"data: train {Xtr.shape}  test {Xte.shape}  classes {sorted(set(ytr))}")
N, D = Xtr.shape

def report(name, acc, model_vals, train_s, note=""):
    # model_vals = number of stored numbers that constitute "the model"
    print(f"  {name:<34} acc={acc*100:5.1f}%   model={model_vals:>9,} vals (~{model_vals*4/1024:.0f}KB)   train={train_s:6.2f}s   {note}")

print("\n=== baselines ===")
maj = np.bincount(ytr).argmax()
report("majority-class (predict commonest)", (yte == maj).mean(), 1, 0.0, "the floor any 'learner' must beat")

print("\n=== OUR approach: nearest-shape (quantized features + exact-bin-agreement 1-NN) ===")
# Replicate fv-histogram quantization + ns-sim (count of exactly-equal bins) at scale.
for Q in (4, 8, 16):
    edges = [np.quantile(Xtr[:, j], np.linspace(0, 1, Q + 1)[1:-1]) for j in range(D)]
    Qtr = np.stack([np.digitize(Xtr[:, j], edges[j]) for j in range(D)], 1).astype(np.int8)
    Qte = np.stack([np.digitize(Xte[:, j], edges[j]) for j in range(D)], 1).astype(np.int8)
    t = time.time()
    knn = KNeighborsClassifier(n_neighbors=1, metric="hamming").fit(Qtr, ytr)  # 1-NN by max exact-agreement
    acc = accuracy_score(yte, knn.predict(Qte))
    report(f"nearest-shape Q={Q} (1-NN, all exemplars)", acc, N * D, time.time() - t,
           "NON-PARAMETRIC: 'model' = the whole training set, no compression")

print("\n=== reference: 1-NN on raw continuous features (standard k-NN, no quantization) ===")
t = time.time()
knn = KNeighborsClassifier(n_neighbors=1).fit(Xtr, ytr)
report("1-NN euclidean (raw 561-dim)", accuracy_score(yte, knn.predict(Xte)), N * D, time.time() - t,
       "also a memorizer: model = all data")

print("\n=== SMALL PARAMETRIC models (the 'small model' candidates — but need floats + multiply) ===")
t = time.time()
lr = LogisticRegression(max_iter=2000, C=1.0).fit(Xtr, ytr)
report("logistic regression (linear)", accuracy_score(yte, lr.predict(Xte)), (D + 1) * 6, time.time() - t,
       f"{(D+1)*6:,} params — a genuinely SMALL model")
t = time.time()
svc = LinearSVC(C=1.0, max_iter=5000).fit(Xtr, ytr)
report("linear SVM", accuracy_score(yte, svc.predict(Xte)), (D + 1) * 6, time.time() - t, "~SOTA-classical")
t = time.time()
mlp = MLPClassifier(hidden_layer_sizes=(64,), max_iter=400, random_state=0).fit(Xtr, ytr)
nparams = D * 64 + 64 + 64 * 6 + 6
report("MLP (1 hidden layer of 64)", accuracy_score(yte, mlp.predict(Xte)), nparams, time.time() - t,
       f"{nparams:,} params")

print("\n=== LEARNING CURVE — does nearest-shape generalize as data grows, or sit at the floor? ===")
rng = np.random.default_rng(0)
Q = 8
edges = [np.quantile(Xtr[:, j], np.linspace(0, 1, Q + 1)[1:-1]) for j in range(D)]
Qtr_all = np.stack([np.digitize(Xtr[:, j], edges[j]) for j in range(D)], 1).astype(np.int8)
Qte = np.stack([np.digitize(Xte[:, j], edges[j]) for j in range(D)], 1).astype(np.int8)
perm = rng.permutation(N)
print("  exemplars  test-acc  (held-out 2947; this is generalization, not memorized-train)")
for n in (10, 30, 100, 300, 1000, 3000, N):
    idx = perm[:n]
    knn = KNeighborsClassifier(n_neighbors=1, metric="hamming").fit(Qtr_all[idx], ytr[idx])
    acc = accuracy_score(yte, knn.predict(Qte))
    print(f"  {n:>9,}  {acc*100:5.1f}%")

print("\n=== published SOTA on UCI-HAR (for scale) ===")
print("  classical SVM/RF on the 561 features ......... ~96%")
print("  CNN / LSTM / deep models ...................... ~96-97%  (~50k-1M params)")
print("  best ensembles ................................ ~97%+")
