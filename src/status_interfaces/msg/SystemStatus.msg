# System wall-clock sampling time; use_sim_time is unsupported.
builtin_interfaces/Time stamp
string hostname
# Overall utilization, percent (0..100).
float32 cpu_percent
float32 memory_percent
# Total and available memory, GiB (bytes / 1024^3).
float32 memory_total
float32 memory_available
# OS cumulative network counters, MiB (bytes / 1024^2), all interfaces.
float32 net_sent
float32 net_recv
