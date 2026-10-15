"""Observed workbook citations must lead to the declared implementation."""
import build_feature_tracker as tracker


def test_unrelated_global_fps_constant_does_not_replace_cache_implementation():
    refs = tracker._source_line_refs(
        "ui/workers.py / services/pipeline.py / core/render_cache.py / core/models.py",
        "Cached SceneBundle media profile includes FPS and render_profile_key; pipeline and worker retain source code.")
    assert "tools/build_ent_acceleration_cloud_video.py" not in refs
    assert "aetherlab/core/render_cache.py:" in refs
    assert "aetherlab/services/pipeline.py:" in refs or "aetherlab/ui/workers.py:" in refs


def test_explicit_reexport_keeps_the_actual_command_bar_definition():
    refs = tracker._source_line_refs("ui/widgets.py", "CommandBar._submit() emits a prompt")
    assert "aetherlab/ui/command_bar.py:" in refs


def test_explicit_profile_source_is_not_displaced_by_global_fps_symbol():
    refs = tracker._source_line_refs("core/render_profile.py", "FPS and dimensions control the render profile")
    assert "tools/" not in refs
    assert "aetherlab/core/render_profile.py:" in refs


def test_cache_story_links_to_actual_pipeline_entry_points():
    import ast
    row = next(item for item in tracker.FEATURES if item[0] == "F33")
    for filename, class_name, method in (("aetherlab/services/pipeline.py", "AetherLabPipeline", "run"),
            ("aetherlab/ui/workers.py", "PipelineWorker", "_run_async")):
        tree = ast.parse((tracker.ROOT / filename).read_text(encoding="utf-8"))
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == class_name)
        target = next(node for node in cls.body if isinstance(node, ast.AsyncFunctionDef) and node.name == method)
        assert f"{filename}:{target.lineno}" in row[11]


def test_unt_policy_cites_duration_implementation_instead_of_a_storyboard_field():
    import ast

    row = next(item for item in tracker.FEATURES if item[0] == "F256")
    filename = "aetherlab/services/manim_runtime.py"
    tree = ast.parse((tracker.ROOT / filename).read_text(encoding="utf-8"))
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                    and node.name == "_duration_contract_delta")
    assert f"{filename}:{function.lineno}" in row[11]


def test_spider_patch_story_cites_validation_and_apply_implementation():
    import ast

    row = next(item for item in tracker.FEATURES if item[0] == "F258")
    for filename, names in (("aetherlab/services/spider.py", {"_patch_paths", "_apply_patch"}),
                            ("aetherlab/core/proc.py", {"subprocess_kwargs"})):
        tree = ast.parse((tracker.ROOT / filename).read_text(encoding="utf-8"))
        for function in tree.body:
            if isinstance(function, ast.FunctionDef) and function.name in names:
                assert f"{filename}:{function.lineno}" in row[11]


def test_spider_feedback_scope_does_not_invent_widget_or_signal_execution(monkeypatch):
    monkeypatch.setattr(tracker, "FEATURES", list(tracker.FEATURES))
    note = "5 owned callback/service checks; no actual widget or signal journey"
    tracker.apply_results({"F259": {"status": "PASS", "note": note, "checked_at": "2026-10-15T00:00:00Z"}})
    result = next(item for item in tracker.FEATURES if item[0] == "F259")
    assert result[18] == note
    assert result[19] == "PARTIAL"
    assert "in-flight Git" in result[20]


def test_sidebar_inventory_describes_all_nine_current_destinations():
    import ast
    source = tracker.ROOT / "aetherlab/ui/navigation.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    sidebar = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "SidebarNav")
    items = next(node.value for node in sidebar.body if isinstance(node, ast.Assign)
                 and any(isinstance(target, ast.Name) and target.id == "_ITEMS" for target in node.targets))
    assert isinstance(items, ast.List) and len(items.elts) == 9
    row = next(item for item in tracker.FEATURES if item[0] == "F75")
    assert "nine" in row[3] and "nine" in row[4] and "nine" in row[9]
    assert "5 rail items" not in row[3]
