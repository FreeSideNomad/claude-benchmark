from harness.lib.worktree import create_worktree, remove_worktree


def test_create_worktree_copies_seed_content(tmp_path):
    seed_dir = tmp_path / "seed"
    work_dir = tmp_path / "work"
    seed_dir.mkdir()
    (seed_dir / "hello.txt").write_text("hello\n")
    (seed_dir / "sub").mkdir()
    (seed_dir / "sub" / "nested.txt").write_text("nested\n")

    create_worktree(seed_dir, work_dir)

    assert (work_dir / "hello.txt").read_text() == "hello\n"
    assert (work_dir / "sub" / "nested.txt").read_text() == "nested\n"


def test_remove_worktree_deletes_work_dir(tmp_path):
    seed_dir = tmp_path / "seed"
    work_dir = tmp_path / "work"
    seed_dir.mkdir()
    (seed_dir / "hello.txt").write_text("hello\n")
    create_worktree(seed_dir, work_dir)

    remove_worktree(work_dir)

    assert not work_dir.exists()


def test_remove_worktree_is_safe_if_already_missing(tmp_path):
    remove_worktree(tmp_path / "does-not-exist")
