from jarvis_cli.benchmark_fixtures import create_core_fixture
from jarvis_cli.repository_graph import RepositoryGraph
from jarvis_cli.skills import SkillRegistry


def test_seeded_benchmark_fixture_is_structurally_useful(tmp_path):
    root = create_core_fixture(tmp_path / "fixture")
    assert (root / "src/auth.py").is_file()
    assert (root / "tests/test_parser.py").is_file()
    assert (root / "UNTRUSTED.md").is_file()
    graph = RepositoryGraph(root)
    graph.update()
    assert graph.find_symbol("AuthService")
    assert graph.related_tests("src/auth.py") == ["tests/test_auth.py"]
    assert {item.name for item in SkillRegistry(root).list()} == {
        "deploy",
        "postgres-migration",
    }
