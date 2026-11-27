// Reference classical heuristics for the QvsC Max-Cut track.
//
//   tabu  1-flip tabu search with incremental gains, random tenure, aspiration and
//         perturbation restarts from the best cut (in the spirit of Kochenberger et al. 2013
//         and the BLS family of Benlic & Hao 2013, but deliberately simple).
//   sa    simulated annealing with Metropolis 1-flip moves and a geometric schedule, restarted
//         with doubled length until the budget ends (the classical analogue of quantum annealing).
//   bm    Burer-Monteiro low-rank SDP relaxation solved by the mixing method
//         (Burer, Monteiro & Zhang 2002; Wang, Chang & Kolter 2017), random-hyperplane
//         rounding (Goemans-Williamson) and 1-flip local search, restarted until the budget ends.
//   exact Gray-code enumeration of all cuts, for n <= 34: certifies the optimum of small instances.
//
// Build:  g++ -O3 -std=c++17 -o maxcut_heur maxcut_heur.cpp
// Run:    zcat G1.mc.gz | ./maxcut_heur tabu - --time 10 --seed 1 --out G1.sol --trajectory G1.traj
//
// Input: rudy / G-set format ("n m" then "u v w", 1-based, '#' comments). Output: the vertices
// of one side of the best cut (1-based), and one JSON line on stdout. With --trajectory, every
// improvement of the best cut is logged as "time_s cut", so time-to-target can be computed later
// for any target value.

#include <algorithm>
#include <chrono>
#include <climits>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iostream>
#include <map>
#include <random>
#include <sstream>
#include <string>
#include <vector>

using namespace std;
typedef long long ll;
// tabu parameters (fractions of n): tenure, iterations without improvement before a perturbation,
// number of random flips in a perturbation. Defaults tuned on a few G-set graphs.
static double g_tfrac = 0.1, g_stall = 10, g_pert = 0.1;

struct Graph {
    int n = 0;
    vector<int> off, adj;
    vector<ll> w;
};

static Graph read_graph(istream &in) {
    string line;
    int n = -1;
    map<pair<int, int>, ll> acc;
    while (getline(in, line)) {
        auto h = line.find('#');
        if (h != string::npos) line = line.substr(0, h);
        istringstream ss(line);
        string a;
        if (!(ss >> a)) continue;
        if (a[0] == 'c' || a[0] == '%') continue;
        if (n < 0) { n = stoi(a); continue; }
        int u = stoi(a), v;
        double wd = 1;
        ss >> v;
        if (!(ss >> wd)) wd = 1;
        if (u == v) continue;
        if (u > v) swap(u, v);
        acc[{u - 1, v - 1}] += (ll)llround(wd);
    }
    Graph g;
    g.n = n;
    vector<int> deg(n, 0);
    for (auto &kv : acc) if (kv.second) { deg[kv.first.first]++; deg[kv.first.second]++; }
    g.off.assign(n + 1, 0);
    for (int i = 0; i < n; i++) g.off[i + 1] = g.off[i] + deg[i];
    g.adj.resize(g.off[n]);
    g.w.resize(g.off[n]);
    vector<int> pos(g.off.begin(), g.off.end() - 1);
    for (auto &kv : acc) {
        if (!kv.second) continue;
        int u = kv.first.first, v = kv.first.second;
        g.adj[pos[u]] = v; g.w[pos[u]++] = kv.second;
        g.adj[pos[v]] = u; g.w[pos[v]++] = kv.second;
    }
    return g;
}

struct Clock {
    chrono::steady_clock::time_point t0 = chrono::steady_clock::now();
    double now() const { return chrono::duration<double>(chrono::steady_clock::now() - t0).count(); }
};

struct Best {
    ll cut = LLONG_MIN;
    vector<char> x;
    double t = 0;
    vector<pair<double, ll>> traj;
    bool offer(const vector<char> &y, ll c, double t_) {
        if (c <= cut) return false;
        cut = c; x = y; t = t_;
        traj.push_back({t_, c});
        return true;
    }
};

// cut value and flip gains of a 0/1 assignment
static ll init_gains(const Graph &g, const vector<char> &x, vector<ll> &gain) {
    ll cut = 0;
    gain.assign(g.n, 0);
    for (int i = 0; i < g.n; i++)
        for (int k = g.off[i]; k < g.off[i + 1]; k++) {
            int j = g.adj[k];
            ll w = g.w[k];
            if (x[i] != x[j]) { gain[i] -= w; if (i < j) cut += w; }
            else gain[i] += w;
        }
    return cut;
}

static inline void flip(const Graph &g, vector<char> &x, vector<ll> &gain, int i) {
    x[i] ^= 1;
    gain[i] = -gain[i];
    for (int k = g.off[i]; k < g.off[i + 1]; k++) {
        int j = g.adj[k];
        // edge (i,j) became cut if now different: flipping j would now lose w instead of gaining it
        gain[j] += (x[i] != x[j]) ? -2 * g.w[k] : 2 * g.w[k];
    }
}

// steepest-ascent 1-flip local search to a local optimum
static ll local_search(const Graph &g, vector<char> &x, vector<ll> &gain, ll cut) {
    vector<int> stack;
    vector<char> in(g.n, 0);
    for (int i = 0; i < g.n; i++) if (gain[i] > 0) { stack.push_back(i); in[i] = 1; }
    while (!stack.empty()) {
        int i = stack.back(); stack.pop_back(); in[i] = 0;
        if (gain[i] <= 0) continue;
        cut += gain[i];
        flip(g, x, gain, i);
        for (int k = g.off[i]; k < g.off[i + 1]; k++) {
            int j = g.adj[k];
            if (gain[j] > 0 && !in[j]) { in[j] = 1; stack.push_back(j); }
        }
    }
    return cut;
}

static void run_tabu(const Graph &g, double tlimit, ll target, mt19937_64 &rng, Best &best, Clock &clk) {
    int n = g.n;
    vector<char> x(n);
    for (auto &v : x) v = rng() & 1;
    vector<ll> gain;
    ll cut = init_gains(g, x, gain);
    cut = local_search(g, x, gain, cut);
    best.offer(x, cut, clk.now());
    vector<ll> tabu_until(n, 0);
    ll it = 0, last_improve = 0;
    const ll stall = (ll)(g_stall * n);
    const int tmin = max(1, (int)(n * g_tfrac));
    while (true) {
        if ((it & 255) == 0 && clk.now() >= tlimit) break;
        if (target != LLONG_MIN && best.cut >= target) break;
        it++;
        int bi = -1;
        ll bg = LLONG_MIN;
        int ties = 0;
        for (int i = 0; i < n; i++) {
            ll gi = gain[i];
            bool allowed = tabu_until[i] <= it || cut + gi > best.cut;
            if (!allowed) continue;
            if (gi > bg) { bg = gi; bi = i; ties = 1; }
            else if (gi == bg && (rng() % (++ties)) == 0) bi = i;
        }
        if (bi < 0) { bi = rng() % n; bg = gain[bi]; }
        cut += bg;
        flip(g, x, gain, bi);
        tabu_until[bi] = it + tmin + (ll)(rng() % 15);
        if (cut > best.cut) { best.offer(x, cut, clk.now()); last_improve = it; }
        if (it - last_improve > stall) {  // perturb the best solution and continue
            x = best.x;
            cut = init_gains(g, x, gain);
            int k = max(2, (int)(n * g_pert));
            for (int r = 0; r < k; r++) { int i = rng() % n; cut += gain[i]; flip(g, x, gain, i); }
            fill(tabu_until.begin(), tabu_until.end(), 0);
            last_improve = it;
        }
    }
}

// simulated annealing with 1-flip Metropolis moves; geometric schedule in beta, scaled to the
// instance's gains and weights; anytime: restarts with a doubled number of sweeps until the budget ends.
static void run_sa(const Graph &g, double tlimit, ll target, mt19937_64 &rng, Best &best, Clock &clk) {
    int n = g.n;
    // schedule: start hot (beta0 = 0.3 / mean |gain| of a random assignment), end cold enough
    // that even the smallest nonzero weight change is rarely accepted (beta1 = 7 / min |w|)
    double wmin = 1e300;
    for (ll w : g.w) if (w) wmin = min(wmin, fabs((double)w));
    if (wmin > 1e299) wmin = 1;
    double gmean = 0;
    {
        vector<char> y(n);
        for (auto &v : y) v = rng() & 1;
        vector<ll> gy;
        init_gains(g, y, gy);
        for (ll v : gy) gmean += fabs((double)v);
        gmean = max(gmean / max(1, n), wmin);
    }
    const double b0 = 0.3 / gmean, b1 = max(7.0 / wmin, 2 * b0);
    uniform_real_distribution<double> U(0, 1);
    vector<char> x(n);
    vector<ll> gain;
    ll sweeps = 100;
    while (clk.now() < tlimit && !(target != LLONG_MIN && best.cut >= target)) {
        for (auto &v : x) v = rng() & 1;
        ll cut = init_gains(g, x, gain);
        bool stop = false;
        for (ll s = 0; s < sweeps && !stop; s++) {
            double beta = b0 * pow(b1 / b0, (double)s / max<ll>(1, sweeps - 1));
            for (int k = 0; k < n; k++) {
                int i = rng() % n;
                ll gi = gain[i];
                if (gi >= 0 || U(rng) < exp(beta * gi)) {
                    cut += gi;
                    flip(g, x, gain, i);
                    if (cut > best.cut) best.offer(x, cut, clk.now());
                }
            }
            if ((s & 7) == 0 && (clk.now() >= tlimit || (target != LLONG_MIN && best.cut >= target))) stop = true;
        }
        cut = local_search(g, x, gain, cut);
        best.offer(x, cut, clk.now());
        sweeps *= 2;
    }
}

static void run_bm(const Graph &g, double tlimit, ll target, mt19937_64 &rng, Best &best, Clock &clk) {
    int n = g.n;
    int r = min(16, (int)ceil(sqrt(2.0 * n)) + 1);
    normal_distribution<double> N01(0, 1);
    vector<double> V((size_t)n * r), gv(r), z(r);
    vector<char> x(n);
    vector<ll> gain;
    while (clk.now() < tlimit && !(target != LLONG_MIN && best.cut >= target)) {
        for (int i = 0; i < n; i++) {
            double s = 0;
            for (int a = 0; a < r; a++) { V[(size_t)i * r + a] = N01(rng); s += V[(size_t)i * r + a] * V[(size_t)i * r + a]; }
            s = sqrt(s);
            for (int a = 0; a < r; a++) V[(size_t)i * r + a] /= s;
        }
        // mixing method: v_i <- -normalize(sum_j w_ij v_j), minimises sum w_ij <v_i, v_j>
        double prev = 1e300;
        for (int sweep = 0; sweep < 200; sweep++) {
            double obj = 0;
            for (int i = 0; i < n; i++) {
                fill(gv.begin(), gv.end(), 0.0);
                for (int k = g.off[i]; k < g.off[i + 1]; k++) {
                    const double *vj = &V[(size_t)g.adj[k] * r];
                    double w = (double)g.w[k];
                    for (int a = 0; a < r; a++) gv[a] += w * vj[a];
                }
                double s = 0;
                for (int a = 0; a < r; a++) s += gv[a] * gv[a];
                s = sqrt(s);
                if (s < 1e-12) continue;
                double *vi = &V[(size_t)i * r];
                for (int a = 0; a < r; a++) vi[a] = -gv[a] / s;
                obj -= s;
            }
            if (fabs(prev - obj) <= 1e-5 * fabs(obj)) break;
            prev = obj;
            if (clk.now() >= tlimit) break;
        }
        // random hyperplane rounding + local search
        for (int rep = 0; rep < 32; rep++) {
            for (int a = 0; a < r; a++) z[a] = N01(rng);
            for (int i = 0; i < n; i++) {
                double s = 0;
                for (int a = 0; a < r; a++) s += V[(size_t)i * r + a] * z[a];
                x[i] = s > 0;
            }
            ll cut = init_gains(g, x, gain);
            cut = local_search(g, x, gain, cut);
            best.offer(x, cut, clk.now());
            if (clk.now() >= tlimit) break;
        }
    }
}

// exact: Gray-code enumeration of all 2^(n-1) cuts (vertex n fixed), O(deg) per step. n <= 34.
static void run_exact(const Graph &g, Best &best, Clock &clk) {
    int n = g.n;
    if (n > 34) { fprintf(stderr, "exact enumeration is limited to n <= 34\n"); exit(2); }
    vector<char> x(n, 0);
    vector<ll> gain;
    ll cut = init_gains(g, x, gain), bc = cut;
    unsigned long long bestcode = 0, code = 0, steps = n ? (1ULL << (n - 1)) : 1;
    for (unsigned long long k = 1; k < steps; k++) {
        int i = __builtin_ctzll(k);
        cut += gain[i];
        flip(g, x, gain, i);
        code ^= 1ULL << i;
        if (cut > bc) { bc = cut; bestcode = code; }
    }
    for (int i = 0; i < n; i++) x[i] = (bestcode >> i) & 1;
    best.offer(x, bc, clk.now());
}

int main(int argc, char **argv) {
    if (argc < 3) {
        fprintf(stderr, "usage: %s tabu|sa|bm|exact FILE|- [--time S] [--seed K] [--target T] [--out F] [--trajectory F] [--tenure F --stall F --pert F]\n", argv[0]);
        return 2;
    }
    string algo = argv[1], file = argv[2], out, trajf;
    double tlimit = 10;
    unsigned long long seed = 1;
    ll target = LLONG_MIN;
    for (int i = 3; i < argc; i++) {
        string a = argv[i];
        if (a == "--time") tlimit = atof(argv[++i]);
        else if (a == "--seed") seed = strtoull(argv[++i], 0, 10);
        else if (a == "--target") target = atoll(argv[++i]);
        else if (a == "--out") out = argv[++i];
        else if (a == "--trajectory") trajf = argv[++i];
        else if (a == "--tenure") g_tfrac = atof(argv[++i]);
        else if (a == "--stall") g_stall = atof(argv[++i]);
        else if (a == "--pert") g_pert = atof(argv[++i]);
    }
    Clock clk;
    Graph g;
    if (file == "-") g = read_graph(cin);
    else { ifstream f(file); g = read_graph(f); }
    clk = Clock();  // budget excludes reading the file
    mt19937_64 rng(seed);
    Best best;
    if (algo == "tabu") run_tabu(g, tlimit, target, rng, best, clk);
    else if (algo == "bm") run_bm(g, tlimit, target, rng, best, clk);
    else if (algo == "sa") run_sa(g, tlimit, target, rng, best, clk);
    else if (algo == "exact") run_exact(g, best, clk);
    else { fprintf(stderr, "unknown algorithm %s\n", algo.c_str()); return 2; }
    double total = clk.now();
    if (!out.empty()) {
        // list the smaller side
        int ones = 0;
        for (char c : best.x) ones += c;
        char side = ones * 2 <= g.n ? 1 : 0;
        FILE *f = fopen(out.c_str(), "w");
        fprintf(f, "# cut = %lld (%s, seed %llu)\n", best.cut, algo.c_str(), seed);
        for (int i = 0; i < g.n; i++) if (best.x[i] == side) fprintf(f, "%d\n", i + 1);
        fclose(f);
    }
    if (!trajf.empty()) {
        FILE *f = fopen(trajf.c_str(), "w");
        for (auto &p : best.traj) fprintf(f, "%.6f %lld\n", p.first, p.second);
        fclose(f);
    }
    printf("{\"cut\": %lld, \"time_to_best\": %.6f, \"total_time\": %.6f, \"seed\": %llu}\n", best.cut, best.t, total, seed);
    return 0;
}
