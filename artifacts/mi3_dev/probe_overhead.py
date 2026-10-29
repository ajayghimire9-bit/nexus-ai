import time, sys
from nexus import mi3_accept as A, mi2_learner as M2
for s, f in [(28402, "MUL"), (28402, "SUBH"), (28400, "MUL")]:
    c0 = time.process_time(); ep = A.Episode3(s, f); c1 = time.process_time()
    L = M2.LearnerMI2(ep.train, ep.y_train, ep.query, seed=s, max_s=4); c2 = time.process_time()
    print(s, f, "episode", round(c1 - c0, 2), "learner_init", round(c2 - c1, 2), "train", len(ep.train), "queries", ep.n_queries, flush=True)
