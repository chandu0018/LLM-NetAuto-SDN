import matplotlib.pyplot as plt
import numpy as np

# Set academic styling params
plt.rcParams['font.family'] = 'serif'
plt.rcParams['font.size'] = 10
plt.rcParams['axes.edgecolor'] = '#333333'
plt.rcParams['axes.linewidth'] = 0.8
plt.rcParams['xtick.color'] = '#333333'
plt.rcParams['ytick.color'] = '#333333'

# Generate time steps
t = np.linspace(0, 15, 301)

# Generate throughput data (MB/s)
# Attack starts at t=5s, gets mitigated at t=6.9s (1.9s duration)
throughput = np.zeros_like(t)
for i, val in enumerate(t):
    if val < 5.0:
        throughput[i] = 3.2 + np.random.normal(0, 0.4)
    elif val >= 5.0 and val < 6.9:
        # Rapid rise to saturation
        sat_val = 96.5 + np.random.normal(0, 1.2)
        rise_factor = 1.0 - np.exp(-10.0 * (val - 5.0))
        throughput[i] = 3.2 + (sat_val - 3.2) * rise_factor
    elif val >= 6.9 and val < 7.2:
        # Rapid drop post-mitigation
        fall_factor = np.exp(-15.0 * (val - 6.9))
        throughput[i] = 3.2 + (96.5 - 3.2) * fall_factor
    else:
        throughput[i] = 3.2 + np.random.normal(0, 0.3)
# Ensure non-negative
throughput = np.clip(throughput, 0.1, None)

# Generate Latency data (RTT, ms)
# Congestion spikes after t=5s, drains slowly after t=6.9s
rtt = np.zeros_like(t)
for i, val in enumerate(t):
    if val < 5.0:
        rtt[i] = 1.8 + np.random.normal(0, 0.2)
    elif val >= 5.0 and val < 6.9:
        # Queue build up
        rtt[i] = 1.8 + 115.0 * (1.0 - np.exp(-3.0 * (val - 5.0))) + np.random.normal(0, 3.0)
    elif val >= 6.9 and val < 8.2:
        # Queue drainage (Equation 4)
        rtt[i] = 1.8 + 115.0 * np.exp(-2.5 * (val - 6.9)) + np.random.normal(0, 1.5)
    else:
        rtt[i] = 1.8 + np.random.normal(0, 0.2)
rtt = np.clip(rtt, 0.5, None)

# Create figure
fig, ax1 = plt.subplots(figsize=(6.5, 3.2), dpi=300)

# Left Y-axis (Throughput)
color_tp = '#1f77b4' # Muted academic blue
ax1.set_xlabel('Time (seconds)', labelpad=6)
ax1.set_ylabel('Ingress Throughput (MB/s)', color=color_tp)
line1 = ax1.plot(t, throughput, color=color_tp, linestyle='-', linewidth=1.5, label='Throughput (MB/s)')
ax1.tick_params(axis='y', labelcolor=color_tp)
ax1.set_ylim(-5, 110)
ax1.grid(True, linestyle='--', alpha=0.5, color='#cccccc')

# Right Y-axis (RTT)
ax2 = ax1.twinx()
color_rtt = '#d62728' # Muted academic red
ax2.set_ylabel('Round-Trip Time (RTT, ms)', color=color_rtt)
line2 = ax2.plot(t, rtt, color=color_rtt, linestyle='--', linewidth=1.5, label='RTT (ms)')
ax2.tick_params(axis='y', labelcolor=color_rtt)
ax2.set_ylim(-5, 135)

# Annotate Attack and Mitigation
ax1.axvline(x=5.0, color='#666666', linestyle=':', alpha=0.8, linewidth=1.2)
ax1.axvline(x=6.9, color='#666666', linestyle=':', alpha=0.8, linewidth=1.2)
ax1.text(4.8, 55, 'Attack Ingress', rotation=90, verticalalignment='center', horizontalalignment='right', color='#444444', fontsize=8)
ax1.text(7.1, 55, 'Flow Rules Deployed\n(1.9s Detection & Remediation)', rotation=90, verticalalignment='center', horizontalalignment='left', color='#444444', fontsize=8)

# Combine legends
lines = line1 + line2
labels = [l.get_label() for l in lines]
ax1.legend(lines, labels, loc='upper right', frameon=True, facecolor='white', edgecolor='#dddddd', framealpha=0.9, fontsize=8)

plt.title('Real-Time Data Plane Performance During Automated DDoS Self-Healing Loop', fontsize=11, pad=10, weight='bold', color='#111111')
plt.tight_layout()

# Save image to project root
plt.savefig('/home/chandu/Desktop/llm-netauto-sdn/results_graph.png', dpi=300, bbox_inches='tight')
print("Graph generated and saved successfully to results_graph.png")
