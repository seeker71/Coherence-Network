# Round 4: the GDL move — intern each exemplar's translation ORBIT (equivariance as memory).
import numpy as np, time
from sklearn.datasets import load_digits
from sklearn.linear_model import LogisticRegression
from sklearn.neural_network import MLPClassifier
from sklearn.svm import SVC
from sklearn.neighbors import KNeighborsClassifier
import warnings; warnings.filterwarnings("ignore")
X, y = load_digits(return_X_y=True)

def orbit(img):  # the input + its 4 one-pixel translations (the symmetry group's local orbit)
    g = img.reshape(8,8); outs = [g]
    for ax, d in ((0,1),(0,-1),(1,1),(1,-1)):
        s = np.roll(g, d, axis=ax)
        if ax == 0: s[0 if d==1 else -1, :] = 0
        else:       s[:, 0 if d==1 else -1] = 0
        outs.append(s)
    return [o.ravel().astype(float) for o in outs]

class FormProto4:
    """Exemplar orbit + class prototypes, -L2^2; one pass, no gradients."""
    def __init__(self): self.protos, self.means = [], {}
    def learn(self, x, lab):
        for f in orbit(x): self.protos.insert(0, (lab, f))
        f0 = x.astype(float)
        m, n = self.means.get(lab, (np.zeros(64), 0)); self.means[lab] = (m + f0, n + 1)
    def predict(self, x):
        if not self.protos: return "?"
        f = x.astype(float); sc = {}
        for lab, pf in self.protos:
            s = -float(np.sum((f - pf)**2)); sc[lab] = max(sc.get(lab, -1e18), s)
        for lab, (tot, n) in self.means.items():
            s = -float(np.sum((f - tot/n)**2)); sc[lab] = max(sc[lab], s)
        return max(sc, key=sc.get)
def run(m, Xtr, ytr, Xte, yte):
    for x, l in zip(Xtr, ytr): m.learn(x, l)
    return np.mean([m.predict(x) == t for x, t in zip(Xte, yte)])
BASE = {"1nn-euclid": lambda: KNeighborsClassifier(1), "logreg": lambda: LogisticRegression(max_iter=2000),
        "mlp-sgd": lambda: MLPClassifier((100,), max_iter=2000, random_state=0), "svm-rbf": lambda: SVC(C=10, gamma="scale")}
NS = [10, 20, 50, 100, 200, 500, 1000]
res, times = {}, {}
for seed in range(5):
    rng = np.random.RandomState(seed); idx = rng.permutation(len(X))
    Xs, ys = X[idx], y[idx]; Xte, yte = Xs[1200:], ys[1200:]
    for N in NS:
        Xtr, ytr = Xs[:N], ys[:N]
        for nm, mk in BASE.items():
            t0 = time.time(); m = mk(); m.fit(Xtr, ytr)
            res.setdefault((nm, N), []).append(m.score(Xte, yte))
            times.setdefault((nm, N), []).append(time.time()-t0)
        t0 = time.time()
        res.setdefault(("form-ORBIT", N), []).append(run(FormProto4(), Xtr, ytr, Xte, yte))
        times.setdefault(("form-ORBIT", N), []).append(time.time()-t0)
names = ["form-ORBIT"] + list(BASE)
print(f"{'learner':12s}" + "".join(f"  N={n:<5d}" for n in NS))
for nm in names:
    print(f"{nm:12s}" + "".join(f"  {np.mean(res[(nm, n)])*100:5.1f}  " for n in NS))
print("\nwins vs strongest baseline per N (form-ORBIT - max(baselines)):")
for n in NS:
    best_base = max(np.mean(res[(b, n)]) for b in BASE)
    print(f"  N={n:<5d} delta = {(np.mean(res[('form-ORBIT', n)]) - best_base)*100:+.1f} pp")
