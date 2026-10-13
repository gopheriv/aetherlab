"""Shared worked math for PhysLab's authored fixed mock, not official NCT keys.

International SI symbols are shared by the three language views. The localized
question/explanation provides the meaning and assumptions for these steps.
"""
from __future__ import annotations

MOCK_SOLUTIONS: dict[str, tuple[str, ...]] = {
    "kinematics-velocity-01": (
        r"v=v_0+at", r"v=2+3\cdot4=14\,\mathrm{m/s}",
    ),
    "dynamics-freefall-01": (
        r"v_0=0,\quad v=gt", r"v=10\cdot2=20\,\mathrm{m/s}",
    ),
    "electricity-ohm-01": (
        r"I=\frac{U}{R}", r"I=\frac{12}{6}=2\,\mathrm{A}",
    ),
    "energy-kinetic-01": (
        r"E_k=\frac{mv^2}{2}", r"E_k=\frac{2\cdot3^2}{2}=9\,\mathrm{J}",
    ),
    "waves-period-01": (r"T=\frac{1}{f}", r"T=\frac{1}{5}=0.2\,\mathrm{s}"),
    "statics-moment-01": (
        r"F_1l_1=F_2l_2", r"F_2=\frac{40\cdot0.20}{0.50}=16\,\mathrm{N}",
    ),
    "fluids-pressure-01": (
        r"p=\rho gh", r"p=1000\cdot10\cdot3=30000\,\mathrm{Pa}=30\,\mathrm{kPa}",
    ),
    "mkt-kinetic-energy-01": (
        r"\overline{E_k}=\frac{3}{2}kT", r"\frac{\overline{E_{k,2}}}{\overline{E_{k,1}}}=\frac{600}{300}=2",
    ),
    "gas-law-pressure-01": (
        r"V=\mathrm{const},\quad \frac{p_1}{T_1}=\frac{p_2}{T_2}",
        r"p_2=100\cdot\frac{450}{300}=150\,\mathrm{kPa}",
    ),
    "thermodynamics-first-law-01": (
        r"Q=\Delta U+W", r"W=Q-\Delta U=500-200=300\,\mathrm{J}",
    ),
    "materials-melting-01": (
        r"Q=Lm", r"Q=3.3\cdot10^5\cdot0.50=165000\,\mathrm{J}=165\,\mathrm{kJ}",
    ),
    "electrostatics-distance-01": (
        r"F=k\frac{|q_1q_2|}{r^2}", r"\frac{F_2}{F_1}=\left(\frac{r_1}{2r_1}\right)^2=\frac{1}{4}",
    ),
    "current-media-electrolyte-01": (r"q_+>0,\quad q_-<0",),
    "magnetic-force-parallel-01": (
        r"F=|q|vB\sin\theta", r"\theta=0,\quad \sin0=0,\quad F=0",
    ),
    "induction-emf-01": (
        r"|\varepsilon|=\frac{|\Delta\Phi|}{\Delta t}", r"|\varepsilon|=\frac{0.40}{0.10}=4\,\mathrm{V}",
    ),
    "oscillation-frequency-01": (r"T=\frac{1}{f}", r"T=\frac{1}{2.5}=0.4\,\mathrm{s}"),
    "ac-rms-voltage-01": (
        r"U_{\mathrm{rms}}=\frac{U_{\mathrm{peak}}}{\sqrt{2}}", r"U_{\mathrm{rms}}\approx\frac{311}{1.414}\approx220\,\mathrm{V}",
    ),
    "em-wave-speed-01": (r"v_{\mathrm{radio}}=v_{\mathrm{X}}=c\approx3\cdot10^8\,\mathrm{m/s}",),
    "wave-optics-fringe-01": (
        r"\lambda=500\cdot10^{-9}\,\mathrm{m},\quad d=10^{-3}\,\mathrm{m}",
        r"\Delta x=\frac{\lambda L}{d}=\frac{500\cdot10^{-9}\cdot2}{10^{-3}}=10^{-3}\,\mathrm{m}=1\,\mathrm{mm}",
    ),
    "geometric-optics-lens-01": (
        r"\frac{1}{f}=\frac{1}{d_o}+\frac{1}{d_i}",
        r"\frac{1}{d_i}=\frac{1}{10}-\frac{1}{30}=\frac{1}{15}\,\mathrm{cm}^{-1}",
        r"d_i=15\,\mathrm{cm}",
    ),
    "relativity-gamma-01": (
        r"\gamma=\frac{1}{\sqrt{1-v^2/c^2}}", r"\gamma=\frac{1}{\sqrt{1-0.6^2}}=\frac{1}{0.8}=1.25",
    ),
    "quantum-photon-energy-01": (r"E=hf", r"\frac{E_2}{E_1}=\frac{2f_1}{f_1}=2"),
    "nuclear-half-life-01": (
        r"n=\frac{8}{4}=2", r"\frac{N}{N_0}=\left(\frac{1}{2}\right)^2=\frac{1}{4}",
    ),
    "nanotechnology-surface-ratio-01": (
        r"\frac{S}{V}\propto\frac{l^2}{l^3}=\frac{1}{l}", r"l_2=\frac{l_1}{10},\quad \frac{S_2/V_2}{S_1/V_1}=10",
    ),
    "cosmology-redshift-01": (r"z=\frac{\lambda_{\mathrm{obs}}-\lambda_{\mathrm{emit}}}{\lambda_{\mathrm{emit}}}>0",),
    "context-solar-heater-energy-01": (
        r"\Delta T=30-20=10\,\mathrm{K}", r"Q=cm\Delta T=4200\cdot2\cdot10=84000\,\mathrm{J}=84\,\mathrm{kJ}",
    ),
    "context-solar-heater-power-02": (
        r"t=20\cdot60=1200\,\mathrm{s}", r"P=\frac{E}{t}=\frac{84000}{1200}=70\,\mathrm{W}",
    ),
    "context-solar-heater-height-03": (r"\Delta E_p=mgh=2\cdot10\cdot5=100\,\mathrm{J}",),
    "context-solar-heater-efficiency-04": (r"\eta=\frac{E_{\mathrm{useful}}}{E_{\mathrm{input}}}\cdot100\%=\frac{84}{120}\cdot100\%=70\%",),
    "context-solar-heater-volume-05": (r"p=\rho gh=1000\cdot10\cdot5=50000\,\mathrm{Pa}=50\,\mathrm{kPa}",),
    "multi-kinematics-velocity-01": (r"a=\frac{\Delta v}{\Delta t}", r"a=0\ \Rightarrow\ v=\mathrm{const}"),
    "multi-newton-laws-01": (r"F_{\mathrm{net}}=ma", r"a=\frac{F_{\mathrm{net}}}{m},\quad [F]=\mathrm{N}"),
    "multi-electricity-ohm-01": (r"I=\frac{U}{R}", r"R=\mathrm{const}\ \Rightarrow\ \frac{I_2}{I_1}=\frac{U_2}{U_1}"),
    "multi-energy-conservation-01": (r"E_k+E_p=\mathrm{const}", r"v_{\mathrm{top}}=0,\quad |\vec{a}|=g"),
    "multi-wave-optics-01": (r"f_1=f_2,\quad \Delta\varphi=\mathrm{const}", r"\Delta x=\frac{\lambda L}{d}"),
    "matching-mechanics-units-01": (r"[v]=\mathrm{m/s},\quad [F]=\mathrm{N}",),
    "matching-electricity-units-02": (r"[I]=\mathrm{A},\quad [R]=\Omega",),
    "matching-thermodynamics-processes-03": (r"p=\mathrm{const},\quad V=\mathrm{const}",),
    "matching-optics-images-04": (
        r"d_o>2f\ \Rightarrow\ f<d_i<2f,\quad |M|<1",
        r"f<d_o<2f\ \Rightarrow\ d_i>2f,\quad |M|>1",
    ),
    "matching-radiation-05": (r"\alpha:\ {}^{4}_{2}\mathrm{He},\quad \beta^-:\ e^-",),
}
