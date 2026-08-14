import os
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def load_data(path):
	lines = []
	with open(path, 'r', encoding='utf-8') as fh:
		for raw in fh:
			line = raw.strip()
			if not line:
				continue
			if line.startswith('#'):
				continue
			lines.append(line)

	if len(lines) < 2:
		raise ValueError(f"Not enough data in {path}")

	header = lines[0].split()
	data = [ln.split() for ln in lines[1:]]
	df = pd.DataFrame(data, columns=header).apply(pd.to_numeric)
	df.columns = [c.strip() for c in df.columns]
	return df


def fit_linear(x, y):
	# fit degree-1 polynomial and compute R^2
	coeffs = np.polyfit(x, y, 1)
	p = np.poly1d(coeffs)
	yhat = p(x)
	ss_res = np.sum((y - yhat) ** 2)
	ss_tot = np.sum((y - np.mean(y)) ** 2)
	r2 = 1 - ss_res / ss_tot if ss_tot != 0 else np.nan
	slope = coeffs[0]
	intercept = coeffs[1]
	return slope, intercept, r2, p


def make_plot(df, time_col, data_col, out_path):
	# use second column (V(vset)) as x-axis, but split sections by time
	x_col = df.columns[1]
	# masks for sections by time
	sec1 = (df[time_col] >= 0) & (df[time_col] <= 1.0)
	sec2 = (df[time_col] > 1.0) & (df[time_col] <= 2.0)

	x1 = df.loc[sec1, x_col].values
	y1 = df.loc[sec1, data_col].values
	x2 = df.loc[sec2, x_col].values
	y2 = df.loc[sec2, data_col].values

	s1 = fit_linear(x1, y1) if len(x1) >= 2 else (np.nan, np.nan, np.nan, None)
	s2 = fit_linear(x2, y2) if len(x2) >= 2 else (np.nan, np.nan, np.nan, None)

	try:
		plt.style.use("seaborn-whitegrid")
	except Exception:
		try:
			import seaborn as sns
			sns.set_style("whitegrid")
		except Exception:
			plt.style.use("ggplot")
	fig, axes = plt.subplots(2, 1, figsize=(6.5, 6.5), constrained_layout=True)

	for ax, x, y, s, title in (
		(axes[0], x1, y1, s1, "0–1 s"),
		(axes[1], x2, y2, s2, "1–2 s"),
	):
		slope, intercept, r2, p = s
		ax.scatter(x, y, s=10, color="#2a9d8f", alpha=0.8, label="data")
		if p is not None:
			xs = np.linspace(x.min(), x.max(), 100)
			ax.plot(xs, p(xs), color="#e76f51", lw=2, label=f"fit: y={slope:.3e}x+{intercept:.3e}")
		else:
			ax.text(0.5, 0.5, "insufficient data for fit", transform=ax.transAxes,
					ha="center", va="center")
		ax.set_title(title, fontsize=10)
		ax.set_xlabel(f"{x_col} (Volts)")
		ax.set_ylabel(f"{data_col} (Amps)")
		ax.legend(fontsize=8)
		ax.text(0.02, 0.92, f"slope={slope:.3e}\nR²={r2:.4f}", transform=ax.transAxes,
				fontsize=9, va="top", bbox=dict(boxstyle="round", fc="white", alpha=0.8))

	fig.suptitle("Linear regression on sections (0–1 s and 1–2 s)")
	fig.savefig(out_path, dpi=300)
	print(f"Saved plot to {out_path}")


def main():
	base = Path(__file__).parent
	data_file = base / "Full_Circuit_Randles_Simulation_Results"
	if not data_file.exists():
		raise FileNotFoundError(f"Data file not found: {data_file}")

	df = load_data(data_file)
	# determine column names
	time_col = df.columns[0]
	# use the third column for regression (current)
	data_col = df.columns[2]

	out_path = base / "linear_regression_sections.png"
	make_plot(df, time_col, data_col, out_path)


if __name__ == "__main__":
	main()

