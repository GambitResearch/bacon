SET_ARGS = {
    "subsetof",
    "supersetof",
    "disjointfrom",
    "equals",
    "notsubsetof",
    "notsupersetof",
    "intersects",
    "notequals",
}
HAS_ARGS = {"in", "ni", "hasall", "hasany", "hasonly", "hasnone"}
MULTI_ARG_OPS = HAS_ARGS.union(SET_ARGS)
