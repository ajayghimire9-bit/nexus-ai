from nexus.wave30_skeleton import Archive, Hole, Item, anti_unify, holes, lineage_ablation


def test_anti_unification_types_holes():
    sk = anti_unify([{"op": "map_add", "c": 2}], [{"op": "map_add", "c": 3}])
    assert sk == [{"op": "map_add", "c": Hole("int")}] and holes(sk) == 1
    assert anti_unify([{"op": "diff"}], [{"op": "prefix_sum"}]) is None


def test_lineage_ablation_keeps_dependencies_and_matches_size():
    a = Archive()
    a.add(Item("r", [{"op": "diff"}]))
    a.add(Item("a", [{"op": "map_add", "c": 1}], ("r",)))
    a.add(Item("b", [{"op": "map_add", "c": 2}], ("a",)))
    a.add(Item("x", [{"op": "rotate", "k": 1}]))
    a.add(Item("y", [{"op": "rotate", "k": 2}], ("x",)))
    abl, ctrl = lineage_ablation(a, "b")
    assert set(abl.items) == {"b", "x", "y"} and abl.items["b"].parents == ()
    assert len(ctrl.items) == len(abl.items)
    for arch in (abl, ctrl):
        for it in arch.items.values():
            assert all(p in arch.items for p in it.parents)
