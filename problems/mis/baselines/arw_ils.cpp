// Iterated Local Search for Maximum Independent Set, after
//   D. V. Andrade, M. G. C. Resende, R. F. Werneck,
//   "Fast local search for the maximum independent set problem",
//   Journal of Heuristics 18 (2012) 525-547.
// Reference baseline for QvsC. Single file, no dependencies:
//   g++ -O2 -std=c++17 -o arw_ils arw_ils.cpp
// Usage:
//   arw_ils GRAPH.gph [--time SECONDS] [--seed S] [--target K] [--out FILE]
//   (GRAPH may be '-' to read DIMACS from stdin)
// Prints one JSON line with size, time-to-best and iterations on stdout.
#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iostream>
#include <random>
#include <sstream>
#include <string>
#include <vector>

using namespace std;
using Clock = chrono::steady_clock;

struct IndexedSet {  // O(1) insert / erase / random pick
    vector<int> items, pos;
    explicit IndexedSet(int n = 0) : pos(n, -1) {}
    bool has(int v) const { return pos[v] >= 0; }
    void add(int v) { if (pos[v] < 0) { pos[v] = (int)items.size(); items.push_back(v); } }
    void del(int v) {
        int p = pos[v]; if (p < 0) return;
        int last = items.back(); items[p] = last; pos[last] = p; items.pop_back(); pos[v] = -1;
    }
    size_t size() const { return items.size(); }
};

struct Solver {
    int n = 0;
    vector<vector<int>> adj;
    vector<char> inS;
    vector<int> tight, age;
    IndexedSet S, freeV;
    vector<pair<char, int>> log;  // ('+'/'-', v) for undo
    bool logging = false;
    mt19937_64 rng;
    long long iter = 0;

    void init() {
        inS.assign(n, 0); tight.assign(n, 0); age.assign(n, 0);
        S = IndexedSet(n); freeV = IndexedSet(n);
        for (int v = 0; v < n; ++v) freeV.add(v);
    }
    void insert(int v) {
        inS[v] = 1; S.add(v); freeV.del(v); age[v] = (int)iter;
        for (int u : adj[v]) if (++tight[u] == 1 && !inS[u]) freeV.del(u);
        if (logging) log.push_back({'+', v});
    }
    void remove(int v) {
        inS[v] = 0; S.del(v); age[v] = (int)iter;
        for (int u : adj[v]) if (--tight[u] == 0 && !inS[u]) freeV.add(u);
        if (tight[v] == 0) freeV.add(v);
        if (logging) log.push_back({'-', v});
    }
    int rnd(int k) { return (int)(rng() % (unsigned long long)k); }

    void fill_free() { while (freeV.size()) insert(freeV.items[rnd((int)freeV.size())]); }

    // Try a (1,2)-swap around solution vertex x: remove x, add two 1-tight neighbours.
    bool two_improve(int x, vector<int>& L) {
        L.clear();
        for (int u : adj[x]) if (!inS[u] && tight[u] == 1) L.push_back(u);
        if (L.size() < 2) return false;
        remove(x);
        for (size_t i = 0; i < L.size(); ++i) {
            int a = L[i];
            if (inS[a] || tight[a] != 0) continue;
            insert(a);
            if (freeV.size()) { fill_free(); return true; }
            remove(a);
        }
        insert(x);
        return false;
    }

    void local_search() {
        fill_free();
        vector<int> L, order;
        bool improved = true;
        while (improved) {
            improved = false;
            order = S.items;
            shuffle(order.begin(), order.end(), rng);
            for (int x : order) if (inS[x] && two_improve(x, L)) improved = true;
        }
    }

    // Force k non-solution vertices in, evicting their solution neighbours.
    void perturb() {
        int k = 1;
        if (S.size() > 0 && rnd(2 * (int)S.size()) == 0) {
            k = 2; while (k < (int)S.size() && rnd(2) == 0) ++k;  // rare larger kicks
        }
        int last = -1;
        for (int t = 0; t < k; ++t) {
            int best = -1;
            for (int c = 0; c < 4; ++c) {  // prefer the least recently touched candidate
                int v;
                if (last >= 0 && !adj[last].empty() && rnd(2)) {  // stay local: distance-2 vertex
                    int u = adj[last][rnd((int)adj[last].size())];
                    v = adj[u].empty() ? rnd(n) : adj[u][rnd((int)adj[u].size())];
                } else v = rnd(n);
                if (inS[v]) continue;
                if (best < 0 || age[v] < age[best]) best = v;
            }
            if (best < 0) continue;
            for (int u : adj[best]) if (inS[u]) remove(u);
            insert(best);
            last = best;
        }
    }

    void undo() {
        logging = false;
        for (auto it = log.rbegin(); it != log.rend(); ++it) {
            if (it->first == '+') remove(it->second); else insert(it->second);
        }
        log.clear();
    }
};

static bool read_graph(istream& in, Solver& s) {
    string line; int n = -1;
    vector<pair<int, int>> E;
    while (getline(in, line)) {
        if (line.empty() || line[0] == 'c' || line[0] == '%' || line[0] == '#') continue;
        istringstream ss(line); string t; ss >> t;
        if (t == "p") { string fmt; long long m; ss >> fmt >> n >> m; E.reserve((size_t)m); }
        else if (t == "e") {
            int u, v; ss >> u >> v; --u; --v;
            if (n < 0 || u < 0 || v < 0 || u >= n || v >= n) return false;
            if (u != v) E.push_back({u, v});
        }
    }
    if (n < 0) return false;
    s.n = n; s.adj.assign(n, {});
    for (auto& e : E) { s.adj[e.first].push_back(e.second); s.adj[e.second].push_back(e.first); }
    for (auto& a : s.adj) { sort(a.begin(), a.end()); a.erase(unique(a.begin(), a.end()), a.end()); }
    return true;
}

int main(int argc, char** argv) {
    if (argc < 2) { fprintf(stderr, "usage: %s GRAPH.gph [--time s] [--seed s] [--target k] [--out file]\n", argv[0]); return 2; }
    string path = argv[1], out; double tlim = 10; unsigned long long seed = 1; long long target = -1;
    for (int i = 2; i + 1 < argc; i += 2) {
        string k = argv[i];
        if (k == "--time") tlim = atof(argv[i + 1]);
        else if (k == "--seed") seed = strtoull(argv[i + 1], nullptr, 10);
        else if (k == "--target") target = atoll(argv[i + 1]);
        else if (k == "--out") out = argv[i + 1];
        else { fprintf(stderr, "unknown option %s\n", k.c_str()); return 2; }
    }
    Solver s; s.rng.seed(seed);
    bool ok;
    if (path == "-") ok = read_graph(cin, s);
    else { ifstream f(path); if (!f) { fprintf(stderr, "cannot open %s\n", path.c_str()); return 2; } ok = read_graph(f, s); }
    if (!ok) { fprintf(stderr, "bad graph file\n"); return 2; }

    auto t0 = Clock::now();
    auto elapsed = [&] { return chrono::duration<double>(Clock::now() - t0).count(); };
    s.init();
    s.local_search();
    vector<int> best = s.S.items; double t_best = elapsed();
    while (elapsed() < tlim && (target < 0 || (long long)best.size() < target)) {
        ++s.iter;
        size_t cur = s.S.size();
        s.log.clear(); s.logging = true;
        s.perturb();
        s.local_search();
        s.logging = false;
        size_t nw = s.S.size();
        if (nw > best.size()) { best = s.S.items; t_best = elapsed(); }
        if (nw < cur) {  // ARW acceptance: worse solutions kept with probability 1/(1 + d * d_best)
            double d = (double)(cur - nw), db = (double)(best.size() - nw);
            if (uniform_real_distribution<double>(0, 1)(s.rng) >= 1.0 / (1.0 + d * db)) s.undo();
        }
        s.log.clear();
    }
    sort(best.begin(), best.end());
    if (!out.empty()) {
        FILE* f = fopen(out.c_str(), "w");
        fprintf(f, "# QvsC baseline arw_ils seed=%llu time_limit=%g\n# size = %zu\n", seed, tlim, best.size());
        for (int v : best) fprintf(f, "%d\n", v + 1);
        fclose(f);
    }
    printf("{\"size\": %zu, \"time_to_best\": %.4f, \"total_time\": %.4f, \"iterations\": %lld, \"seed\": %llu}\n",
           best.size(), t_best, elapsed(), s.iter, seed);
    return 0;
}
