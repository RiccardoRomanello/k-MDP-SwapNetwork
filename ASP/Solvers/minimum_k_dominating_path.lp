% Minimum r-dominating path.
% The runner sets radius=1 (1-mDP) or radius=2 (2-mDP).
#const radius = 1.

vertex(0..n-1).
edge(V,U) :- edge(U,V).

% Select a simple path.
{ inPath(V) } :- vertex(V).
{ next(U,V) : edge(U,V) } 1 :- inPath(U).
:- next(U,V), not inPath(V).
:- vertex(V), 2 { next(U,V) : edge(U,V) }.

hasPred(V) :- next(_,V).
hasSucc(U) :- next(U,_).
start(V) :- inPath(V), not hasPred(V).
end(V) :- inPath(V), not hasSucc(V).

% Acyclicity plus exactly one start gives one connected simple path.
#edge (U,V) : next(U,V).
:- not 1 { start(V) : vertex(V) } 1.

% A path and its reverse are equivalent; keep one orientation.
:- start(S), end(E), S > E.

% Every vertex must be at distance at most radius from the path.
near(V,0) :- inPath(V).
near(U,D+1) :- near(V,D), edge(U,V), D < radius.
covered(V) :- near(V,_).
:- vertex(V), not covered(V).

#minimize { 1,V : inPath(V) }.

#show inPath/1.
#show start/1.
#show next/2.
