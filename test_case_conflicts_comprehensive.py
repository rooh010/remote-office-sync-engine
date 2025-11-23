"""Comprehensive integration tests for case conflict scenarios."""

import shutil
import subprocess
from pathlib import Path


class CaseConflictTester:
    """Test runner for case conflict scenarios."""

    def __init__(self, left_root="C:/pdrive_local", right_root="P:/"):
        self.left = Path(left_root)
        self.right = Path(right_root)
        self.results = []

    def cleanup(self):
        """Clean up test files and reset state."""
        patterns = ["scenario*.txt", "*CONFLICT*.txt", "test_*.txt", "*manual*.txt", "*debug*.txt"]
        for p in [self.left, self.right]:
            for pattern in patterns:
                for f in p.glob(pattern):
                    try:
                        f.unlink()
                    except Exception as e:
                        print(f"Warning: Could not delete {f}: {e}")
            # Also clean subdirectories
            for subdir in ["subdir", "testdir"]:
                if (p / subdir).exists():
                    for pattern in patterns:
                        for f in (p / subdir).glob(pattern):
                            try:
                                f.unlink()
                            except Exception as e:
                                print(f"Warning: Could not delete {f}: {e}")

        # Clear state database entries for test files
        from remote_office_sync.state_db import StateDB

        db = StateDB("sync_state.db")
        state = db.load_state()
        test_patterns = ["scenario", "test", "manual", "debug"]
        for path in list(state.keys()):
            if any(pattern in path.lower() for pattern in test_patterns):
                del state[path]
        db.save_state(state)

    def sync(self):
        """Run sync and return output."""
        result = subprocess.run(
            ["python", "-m", "remote_office_sync.main", "--config", "config.yaml"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout + result.stderr

    def rename_via_temp(self, path, new_name):
        """Rename file via temp (needed for case-only changes on Windows)."""
        temp_path = path.parent / f"temp_{path.name}"
        shutil.move(str(path), str(temp_path))
        final_path = path.parent / new_name
        shutil.move(str(temp_path), str(final_path))
        return final_path

    def test_scenario_1_both_different_case(self):
        """Test: Both sides change to different cases."""
        print("\n" + "=" * 60)
        print("Scenario 1: Both sides change to different cases")
        print("=" * 60)

        # Setup
        (self.left / "test1.txt").write_text("content1")
        (self.right / "test1.txt").write_text("content1")
        self.sync()

        # Execute
        self.rename_via_temp(self.left / "test1.txt", "TEST1.txt")
        self.rename_via_temp(self.right / "test1.txt", "Test1.txt")

        # Verify
        output = self.sync()
        has_conflict = "Case conflict" in output

        left_files = set(f.name for f in self.left.glob("*est1*.txt"))
        right_files = set(f.name for f in self.right.glob("*est1*.txt"))

        has_main = "TEST1.txt" in left_files and "TEST1.txt" in right_files
        has_conflict_file = any("CONFLICT" in f for f in left_files) and any(
            "CONFLICT" in f for f in right_files
        )

        passed = has_conflict and has_main and has_conflict_file

        print(f"Conflict detected: {has_conflict}")
        print(f"Main file on both sides: {has_main}")
        print(f"Conflict file on both sides: {has_conflict_file}")
        print(f'Result: {"PASS" if passed else "FAIL"}')

        self.results.append(("Scenario 1", passed))
        return passed

    def test_scenario_2_both_same_case(self):
        """Test: Both sides change to same case."""
        print("\n" + "=" * 60)
        print("Scenario 2: Both sides change to same case")
        print("=" * 60)

        # Setup
        (self.left / "test2.txt").write_text("content2")
        (self.right / "test2.txt").write_text("content2")
        self.sync()

        # Execute
        self.rename_via_temp(self.left / "test2.txt", "TEST2.txt")
        self.rename_via_temp(self.right / "test2.txt", "TEST2.txt")

        # Verify
        output = self.sync()
        has_conflict = "Case conflict" in output

        left_files = set(f.name for f in self.left.glob("*est2*.txt"))
        right_files = set(f.name for f in self.right.glob("*est2*.txt"))

        has_main = "TEST2.txt" in left_files and "TEST2.txt" in right_files
        no_conflict_file = not any("CONFLICT" in f for f in left_files | right_files)

        passed = not has_conflict and has_main and no_conflict_file

        print(f"Conflict detected: {has_conflict}")
        print(f"Main file on both sides: {has_main}")
        print(f"No conflict file: {no_conflict_file}")
        print(f'Result: {"PASS" if passed else "FAIL"}')

        self.results.append(("Scenario 2", passed))
        return passed

    def test_scenario_3_one_side_only(self):
        """Test: One side changes case, other unchanged."""
        print("\n" + "=" * 60)
        print("Scenario 3: One side changes case only")
        print("=" * 60)

        # Setup
        (self.left / "test3.txt").write_text("content3")
        (self.right / "test3.txt").write_text("content3")
        self.sync()

        # Execute - only left changes
        self.rename_via_temp(self.left / "test3.txt", "TEST3.txt")

        # Verify
        output = self.sync()
        has_conflict = "Case conflict" in output

        left_files = set(f.name for f in self.left.glob("*est3*.txt"))
        right_files = set(f.name for f in self.right.glob("*est3*.txt"))

        has_main = "TEST3.txt" in left_files and "TEST3.txt" in right_files
        no_conflict_file = not any("CONFLICT" in f for f in left_files | right_files)

        passed = not has_conflict and has_main and no_conflict_file

        print(f"Conflict detected: {has_conflict}")
        print(f"Main file on both sides: {has_main}")
        print(f"No conflict file: {no_conflict_file}")
        print(f'Result: {"PASS" if passed else "FAIL"}')

        self.results.append(("Scenario 3", passed))
        return passed

    def test_scenario_4_mixed_cases(self):
        """Test: Mixed case variations."""
        print("\n" + "=" * 60)
        print("Scenario 4: Mixed case variations")
        print("=" * 60)

        # Setup
        (self.left / "test4.txt").write_text("content4")
        (self.right / "test4.txt").write_text("content4")
        self.sync()

        # Execute - different mixed cases
        self.rename_via_temp(self.left / "test4.txt", "TeSt4.txt")
        self.rename_via_temp(self.right / "test4.txt", "tEsT4.txt")

        # Verify
        output = self.sync()
        has_conflict = "Case conflict" in output

        left_files = set(f.name for f in self.left.glob("*est4*.txt"))
        right_files = set(f.name for f in self.right.glob("*est4*.txt"))

        has_main = "TeSt4.txt" in left_files and "TeSt4.txt" in right_files
        has_conflict_file = any("CONFLICT" in f for f in left_files) and any(
            "CONFLICT" in f for f in right_files
        )

        passed = has_conflict and has_main and has_conflict_file

        print(f"Conflict detected: {has_conflict}")
        print(f"Main file on both sides: {has_main}")
        print(f"Conflict file on both sides: {has_conflict_file}")
        print(f'Result: {"PASS" if passed else "FAIL"}')

        self.results.append(("Scenario 4", passed))
        return passed

    def test_scenario_5_subdirectory(self):
        """Test: Case conflict in subdirectory."""
        print("\n" + "=" * 60)
        print("Scenario 5: Case conflict in subdirectory")
        print("=" * 60)

        # Setup
        (self.left / "subdir").mkdir(exist_ok=True)
        (self.right / "subdir").mkdir(exist_ok=True)
        (self.left / "subdir" / "test5.txt").write_text("content5")
        (self.right / "subdir" / "test5.txt").write_text("content5")
        self.sync()

        # Execute
        self.rename_via_temp(self.left / "subdir" / "test5.txt", "TEST5.txt")
        self.rename_via_temp(self.right / "subdir" / "test5.txt", "Test5.txt")

        # Verify
        output = self.sync()
        has_conflict = "Case conflict" in output

        left_files = set(f.name for f in (self.left / "subdir").glob("*est5*.txt"))
        right_files = set(f.name for f in (self.right / "subdir").glob("*est5*.txt"))

        has_main = "TEST5.txt" in left_files and "TEST5.txt" in right_files
        has_conflict_file = any("CONFLICT" in f for f in left_files) and any(
            "CONFLICT" in f for f in right_files
        )

        passed = has_conflict and has_main and has_conflict_file

        print(f"Conflict detected: {has_conflict}")
        print(f"Main file on both sides: {has_main}")
        print(f"Conflict file on both sides: {has_conflict_file}")
        print(f'Result: {"PASS" if passed else "FAIL"}')

        self.results.append(("Scenario 5", passed))
        return passed

    def run_all(self):
        """Run all test scenarios."""
        print("=" * 60)
        print("COMPREHENSIVE CASE CONFLICT TESTS")
        print("=" * 60)

        # Clean up once at the start
        self.cleanup()

        tests = [
            self.test_scenario_1_both_different_case,
            self.test_scenario_2_both_same_case,
            self.test_scenario_3_one_side_only,
            self.test_scenario_4_mixed_cases,
            self.test_scenario_5_subdirectory,
        ]

        for test in tests:
            try:
                test()
            except Exception as e:
                import traceback

                print(f"ERROR in {test.__name__}: {e}")
                traceback.print_exc()
                self.results.append((test.__name__, False))

        # Print summary
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        for name, passed in self.results:
            status = "PASS" if passed else "FAIL"
            print(f"{name}: {status}")

        total = len(self.results)
        passed_count = sum(1 for _, p in self.results if p)
        print(f"\nTotal: {passed_count}/{total} passed")

        return passed_count == total


if __name__ == "__main__":
    tester = CaseConflictTester()
    all_passed = tester.run_all()
    exit(0 if all_passed else 1)
