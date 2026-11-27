// Exhaustive search for small CNF formulas (n <= 30): enumerates all 2^n assignments in Gray-code
// order, updating the number of true literals of the clauses of the one flipped variable.
//
// It certifies the optimum (minimum number of unsatisfied clauses; 0 = satisfiable) and counts the
// optimal assignments, which gives the success probability of uniform random sampling.
//
// Build:  g++ -O3 -std=c++17 -o exhaustive exhaustive.cpp
// Run:    ./exhaustive x.cnf --out x.sol
//
// Output (--out): the first optimal assignment found, as a bit string (character i = variable i+1),
// and one JSON line on stdout: n, m, optimum_unsat, optimal_assignments, time_to_solution_s (time at
// which the first optimal assignment was met during the enumeration), total_time_s.

#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

using namespace std;

int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "usage: %s FILE.cnf|- [--out F]\n", argv[0]); return 2; }
    string path = argv[1], out;
    for (int i = 2; i + 1 < argc; i++) if (string(argv[i]) == "--out") out = argv[++i];
    ifstream fin;
    if (path != "-") fin.open(path);
    istream &in = path == "-" ? cin : fin;
    int n = 0;
    vector<vector<int>> cl;
    vector<int> cur;
    string line;
    while (getline(in, line)) {
        if (line.empty() || line[0] == 'c') continue;
        if (line[0] == '%') break;
        if (line[0] == 'p') { istringstream ss(line); string p, f; int m; ss >> p >> f >> n >> m; continue; }
        istringstream ss(line);
        int x;
        while (ss >> x) { if (x == 0) { cl.push_back(cur); cur.clear(); } else cur.push_back(x); }
    }
    if (!cur.empty()) cl.push_back(cur);
    if (n > 30) { fprintf(stderr, "n = %d is too large for exhaustive search\n", n); return 2; }
    int m = (int)cl.size();
    vector<vector<pair<int, int>>> occ(n + 1);     // (clause, +1 if positive literal else -1)
    for (int c = 0; c < m; c++) for (int l : cl[c]) occ[abs(l)].push_back({c, l > 0 ? 1 : -1});
    auto t0 = chrono::steady_clock::now();
    vector<char> x(n + 1, 0);
    vector<int> nt(m, 0);
    int unsat = 0;
    for (int c = 0; c < m; c++) {
        for (int l : cl[c]) nt[c] += (l < 0);      // all variables false: negative literals are true
        unsat += nt[c] == 0;
    }
    int best = unsat;
    long long count = 1;
    double tts = 0;
    unsigned long long best_code = 0, code = 0;
    unsigned long long total = 1ULL << n;
    for (unsigned long long i = 1; i < total; i++) {
        int v = __builtin_ctzll(i) + 1;            // Gray code: flip variable v
        x[v] ^= 1;
        code ^= 1ULL << (v - 1);
        for (auto [c, s] : occ[v]) {
            bool now_true = (s > 0) == (bool)x[v];
            if (now_true) { if (nt[c]++ == 0) unsat--; }
            else { if (--nt[c] == 0) unsat++; }
        }
        if (unsat < best) {
            best = unsat; count = 1; best_code = code;
            tts = chrono::duration<double>(chrono::steady_clock::now() - t0).count();
        } else if (unsat == best) count++;
    }
    double tot = chrono::duration<double>(chrono::steady_clock::now() - t0).count();
    if (!out.empty()) {
        ofstream o(out);
        for (int v = 1; v <= n; v++) o << ((best_code >> (v - 1)) & 1 ? '1' : '0');
        o << "\n";
    }
    printf("{\"n\":%d,\"m\":%d,\"optimum_unsat\":%d,\"optimal_assignments\":%lld,\"time_to_solution_s\":%.6f,\"total_time_s\":%.6f}\n",
           n, m, best, count, tts, tot);
    return 0;
}
