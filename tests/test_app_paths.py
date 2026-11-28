from pathlib import Path
import unittest

from app_paths import default_results_directory


class DefaultResultsDirectoryTests(unittest.TestCase):
    def test_windows_uses_local_app_data_not_the_working_directory(self):
        home = Path("C:/Users/qa-user")
        result = default_results_directory(
            environ={"LOCALAPPDATA": "C:/Users/qa-user/AppData/Local"},
            home=home,
            system="Windows",
        )
        self.assertEqual(
            result,
            Path("C:/Users/qa-user/AppData/Local/DataContractAuditor/Results"),
        )

    def test_windows_conventional_fallback_is_per_user(self):
        result = default_results_directory(environ={}, home=Path("C:/Users/qa-user"), system="Windows")
        self.assertEqual(
            result,
            Path("C:/Users/qa-user/AppData/Local/DataContractAuditor/Results"),
        )

    def test_xdg_data_home_is_honored_on_non_windows(self):
        result = default_results_directory(
            environ={"XDG_DATA_HOME": "/tmp/qa-data"}, home=Path("/home/qa-user"), system="Linux"
        )
        self.assertEqual(result, Path("/tmp/qa-data/DataContractAuditor/Results"))


if __name__ == "__main__":
    unittest.main()

