# A/B: the body's learner (one-pass, exemplar+bin-match, style-space) vs standard models.
import numpy as np
from sklearn.datasets import load_digits
from sklearn.linear_model import LogisticRegression
from sklearn.neural_network import MLPClassifier
from sklearn.svm import SVC
from sklearn.neighbors import KNeighborsClassifier
import warnings; warnings.filterwarnings("ignore")

X, y = load_digits(return_X_y=True)   # 1797 x 64, ints 0..16
rng_global = np.random.RandomState(0)

# ---- the body's featurizers (style rows) ----
def f_raw(img):    return tuple(img.astype(int))
def f_tern(img):   return tuple((img > 8).astype(int) + (img > 0).astype(int))
def f_coarse(img): # 2x2 average pool (one grid-diffusion step) then ternarize
    g = img.reshape(8,8)
    p = g.reshape(4,2,4,2).mean(axis=(1,3))
    return tuple((p > 8).astype(int).ravel() + (p > 2).astype(int).ravel())
def f_rowcol(img): # projection profiles, quantized (chart-pool analog)
    g = img.reshape(8,8)
    prof = np.concatenate([g.sum(1), g.sum(0)])
    return tuple((prof / 16).astype(int))
def f_grad(img):   # local gradient signs pooled per quadrant (conv analog)
    g = img.reshape(8,8).astype(float)
    gx, gy = np.gradient(g)
    feats = []
    for qi in range(2):
        for qj in range(2):
            sx = gx[qi*4:qi*4+4, qj*4:qj*4+4]; sy = gy[qi*4:qi*4+4, qj*4:qj*4+4]
            feats += [int(sx.sum()//8), int(sy.sum()//8), int(np.abs(sx).sum()//16), int(np.abs(sy).sum()//16)]
    return tuple(feats)
STYLES = [("raw16", f_raw), ("tern", f_tern), ("coarse", f_coarse), ("rowcol", f_rowcol), ("grad", f_grad)]

def ns_sim(a, b):  # exact bin-match count
    return sum(1 for u, v in zip(a, b) if u == v)

class FormProto:
    """Mirror of the recipes: exemplar interning + bin-match recognition + abstention."""
    def __init__(self, feat): self.feat, self.protos = feat, []
    def predict(self, x, floor=0):
        if not self.protos: return "?"
        f = self.feat(x)
        best, bs = None, -1
        for lab, pf in self.protos:           # first-in-walk wins ties (newest first)
            s = ns_sim(f, pf)
            if s > bs: best, bs = lab, s
        return best if bs >= floor else "?"
    def learn(self, x, lab): self.protos.insert(0, (lab, self.feat(x)))

def run_form(Xtr, ytr, Xte, yte, feat):
    m = FormProto(feat)
    for x, lab in zip(Xtr, ytr): m.learn(x, lab)
    pred = [m.predict(x) for x in Xte]
    return np.mean([p == t for p, t in zip(pred, yte)])

def auto_style(Xtr, ytr, k):
    """ls-research: warmed online agreement on the TRAIN stream picks the style."""
    best, bs = None, -1
    for name, feat in STYLES:
        m, agree = FormProto(feat), 0
        for i, (x, lab) in enumerate(zip(Xtr, ytr)):
            if i >= k and m.predict(x) == lab: agree += 1
            m.learn(x, lab)
        if agree > bs: best, bs = (name, feat), agree
    return best

BASELINES = {
    "1nn-euclid": lambda: KNeighborsClassifier(1),
    "logreg":     lambda: LogisticRegression(max_iter=2000),
    "mlp-sgd":    lambda: MLPClassifier(hidden_layer_sizes=(100,), max_iter=2000, random_state=0),
    "svm-rbf":    lambda: SVC(C=10, gamma="scale"),
}

NS = [10, 20, 50, 100, 200, 500, 1000]
SEEDS = range(5)
results = {}
for seed in SEEDS:
    rng = np.random.RandomState(seed)
    idx = rng.permutation(len(X))
    Xs, ys = X[idx], y[idx]
    Xte, yte = Xs[1200:], ys[1200:]
    for N in NS:
        Xtr, ytr = Xs[:N], ys[:N]
        for bname, mk in BASELINES.items():
            try:
                m = mk(); m.fit(Xtr, ytr)
                acc = m.score(Xte, yte)
            except Exception: acc = float("nan")
            results.setdefault((bname, N), []).append(acc)
        for sname, feat in STYLES:
            results.setdefault((f"form-{sname}", N), []).append(run_form(Xtr, ytr, Xte, yte, feat))
        aname, afeat = auto_style(Xtr, ytr, k=min(5, N // 2))
        results.setdefault(("form-AUTO", N), []).append(run_form(Xtr, ytr, Xte, yte, afeat))
        results.setdefault(("auto-pick", N), []).append(aname)

names = ["form-AUTO"] + [f"form-{s}" for s, _ in STYLES] + list(BASELINES)
print(f"{'learner':14s}" + "".join(f"  N={n:<5d}" for n in NS))
for nm in names:
    row = "".join(f"  {np.mean(results[(nm, n)]) * 100:5.1f}  " for n in NS)
    print(f"{nm:14s}{row}")
print("\nauto-picked styles by N:", {n: sorted(set(results[('auto-pick', n)])) for n in NS})
