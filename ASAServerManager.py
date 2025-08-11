import os
import sys
import subprocess
import platform
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QLineEdit, QLabel, QTextEdit, QStackedWidget, QMainWindow,
    QHBoxLayout
)
from PyQt5.QtGui import QRegExpValidator, QIntValidator
from PyQt5.QtCore import QThread, pyqtSignal, QRegExp, QTimer


steam_cmd_path = ""
install_path = ""
start_bat_content = ""

def resource_path(relative_path):
    # For the temp folder created by PYINSTALLER
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


ps1_path = resource_path("setup-asa-server.ps1")
template_path = resource_path(os.path.join("data", "GameSettingsTemplate.ini"))

class ScriptRunner(QThread):
    finished = pyqtSignal()
    output = pyqtSignal(str)

    def run(self):
        process = subprocess.Popen([
            "powershell", "-ExecutionPolicy", "Bypass", "-File", ps1_path,
            "-steamCmdPath", steam_cmd_path,
            "-installPath", install_path,
            "-startBatContent", start_bat_content
        ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            universal_newlines=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )

        for line in iter(process.stdout.readline, ''):
            if line:
                self.output.emit(line.strip())

        process.stdout.close()
        process.wait()
        self.finished.emit()


class ServerRunner(QThread):
    finished = pyqtSignal()
    output = pyqtSignal(str)

    def run(self):
        process = subprocess.Popen(
            os.path.join(install_path, "ShooterGame\\Binaries\\Win64\\start.bat"),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            shell=True,
            bufsize=1,
            universal_newlines=True
        )

        for line in iter(process.stdout.readline, ''):
            self.output.emit(line.strip())

        process.stdout.close()
        process.wait()
        self.finished.emit()


class ArkManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ARK Server Manager")
        self.setMinimumSize(600, 400)

        self.stacked_widget = QStackedWidget()

        self.server_widget = QWidget()
        self.settings_widget = QWidget()

        self.steamCmdLayout = QHBoxLayout()
        self.steamCmdInput = QLineEdit()
        self.steamCmdOpenDirectoryButton = QPushButton("Open Folder")
        self.steamCmdOpenDirectoryButton.clicked.connect(lambda: self.open_directory(steam_cmd=True))
        self.steamCmdLayout.addWidget(self.steamCmdInput)
        self.steamCmdLayout.addWidget(self.steamCmdOpenDirectoryButton)

        self.arkInstallLayout = QHBoxLayout()
        self.arkInstallInput = QLineEdit()
        self.arkInstallOpenDirectoryButton = QPushButton("Open Folder")
        self.arkInstallOpenDirectoryButton.clicked.connect(lambda: self.open_directory(steam_cmd=False))
        self.arkInstallLayout.addWidget(self.arkInstallInput)
        self.arkInstallLayout.addWidget(self.arkInstallOpenDirectoryButton)

        self.serverNameInput = QLineEdit()
        self.serverAdminPasswordInput = QLineEdit()
        self.serverPasswordInput = QLineEdit()
        self.serverPortInput = QLineEdit()
        self.serverQueryPortInput = QLineEdit()
        self.serverMaxPlayersInput = QLineEdit()
        self.serverLaunchOptionsInput = QLineEdit()

        self.runButton = QPushButton("Install/Update ARK Server")
        self.runButton.clicked.connect(self.run_script)

        self.startServerButton = QPushButton("Start Server")
        self.startServerButton.clicked.connect(self.start_server)

        self.serverSettingsPageButton = QPushButton("Open Settings Files")
        self.serverSettingsPageButton.clicked.connect(self.open_server_settings_page)

        self.textEditor = QTextEdit()
        self.textEditor.setReadOnly(True)

        self.setup_server_run_widget()

        self.onGameUserSettings = True

        self.settingsFileControlPanel = QWidget()
        self.settingsFileControlPanelLayout = QHBoxLayout(self.settingsFileControlPanel)
        self.gameUserSettingsButton = QPushButton("GameUserSettings.ini")
        self.gameUserSettingsButton.clicked.connect(self.switch_to_game_user_settings)
        self.gameSettingsButton = QPushButton("Game.ini")
        self.gameSettingsButton.clicked.connect(self.switch_to_game_settings)
        self.settingsFileControlPanelLayout.addWidget(self.gameUserSettingsButton)
        self.settingsFileControlPanelLayout.addWidget(self.gameSettingsButton)

        self.settingsTextEditor = QTextEdit()
        self.userSettingsTextEditor = QTextEdit()
        self.settingsPageTextEditors = QStackedWidget()
        self.settingsPageTextEditors.addWidget(self.userSettingsTextEditor)
        self.settingsPageTextEditors.addWidget(self.settingsTextEditor)
        self.settingsSaveButton = QPushButton("Save Settings Files")
        self.settingsSaveButton.clicked.connect(lambda: self.save_settings(self.onGameUserSettings))
        self.serverRunPageButton = QPushButton("Install/Run Server")
        self.serverRunPageButton.clicked.connect(self.open_run_server_page)

        self.setup_server_settings_widget()

        self.stacked_widget.addWidget(self.server_widget)
        self.stacked_widget.addWidget(self.settings_widget)

        self.setCentralWidget(self.stacked_widget)

        self.worker = None

        # Set validators for the input fields
        dir_path_validator = QRegExpValidator(QRegExp(r"^[A-Za-z]:[\\/](?:[A-Za-z0-9 _\-\\/]*)$"))
        self.steamCmdInput.setValidator(dir_path_validator)
        self.arkInstallInput.setValidator(dir_path_validator)

        server_name_validator = QRegExpValidator(QRegExp("[A-Za-z0-9_-]+"))
        self.serverNameInput.setValidator(server_name_validator)

        server_admin_password_validator = QRegExpValidator(QRegExp("[A-Za-z0-9!@#$%^*()_+=-]+"))
        self.serverAdminPasswordInput.setValidator(server_admin_password_validator)

        server_port_validator = QIntValidator(1024, 49151)
        self.serverPortInput.setValidator(server_port_validator)
        self.serverQueryPortInput.setValidator(server_port_validator)

        server_max_players_validator = QIntValidator(1, 70)
        self.serverMaxPlayersInput.setValidator(server_max_players_validator)

        # Load user prefs if exists
        self.__load_user_prefs()

    def run_script(self):
        if not self.worker:
            if self.__check_valid_path_inputs() and self.__check_valid_start_bat_inputs():
                self.runButton.setText("Running Script...")
                self.runButton.setEnabled(False)
                # Save the inputs into user preferences to load later
                self.__save_user_prefs()

                global steam_cmd_path, install_path
                steam_cmd_path = self.steamCmdInput.text().strip()
                install_path = self.arkInstallInput.text().strip()

                self.create_start_bat_content()

                self.worker = ScriptRunner()
                self.worker.output.connect(self.append_output)
                self.worker.finished.connect(self.script_done)
                self.worker.start()
            else:
                self.append_output("Server Install Failed.")
        else:
            self.append_output("Cannot install/update server while it is running!")

    def script_done(self):
        self.runButton.setText("Install/Update ARK Server")
        self.runButton.setEnabled(True)
        self.worker = None

    def start_server(self):
        if not self.worker:
            global install_path
            install_path = self.arkInstallInput.text().strip()

            if self.__check_valid_path_inputs(check_steam_cmd=False):
                bat_path = os.path.join(install_path, "ShooterGame\\Binaries\\Win64\\start.bat")
                if os.path.isfile(bat_path):
                    self.startServerButton.setText("Running Server...")
                    self.startServerButton.setEnabled(False)

                    self.worker = ServerRunner()
                    self.worker.output.connect(self.append_output)
                    self.worker.finished.connect(self.server_done)
                    self.worker.start()
                else:
                    self.append_output("Server start.bat file not found at " + bat_path + "!\nInstall/Update server first.")
            else:
                self.append_output("Server Start Failed.")
        else:
            self.append_output("Cannot run server while installing/updating!")

    def server_done(self):
        self.startServerButton.setText("Run ARK Server")
        self.startServerButton.setEnabled(True)

    def switch_to_game_user_settings(self):
        self.onGameUserSettings = True
        self.gameUserSettingsButton.setEnabled(False)
        self.gameSettingsButton.setEnabled(True)
        self.settingsSaveButton.setText("Save GameUserSettings.ini")
        self.settingsSaveButton.setEnabled(False)

        self.settingsPageTextEditors.setCurrentIndex(0)

        global install_path
        install_path = self.arkInstallInput.text().strip()

        if self.__check_valid_path_inputs(check_steam_cmd=False, settings_editor=True):
            game_user_settings_path = os.path.join(install_path, "ShooterGame\\Saved\\Config\\WindowsServer\\GameUserSettings.ini")
            if os.path.isfile(game_user_settings_path):
                try:
                    with open(game_user_settings_path, "r", encoding="utf-8") as f:
                        self.userSettingsTextEditor.setText(f.read())
                        self.settingsSaveButton.setEnabled(True)
                except Exception as e:
                    self.append_output(f"Error reading GameUserSettings.ini: {e}")
            else:
                # Delay the error message slightly to avoid reentrant GUI issues
                QTimer.singleShot(0, lambda: self.append_output(
                    f"Cannot find GameUserSettings.ini at {game_user_settings_path}\nRun and join the server first, then shut it down properly to create the settings files.", settings_editor=True
                ))
    def switch_to_game_settings(self):
        self.onGameUserSettings = False
        self.gameUserSettingsButton.setEnabled(True)
        self.gameSettingsButton.setEnabled(False)
        self.settingsSaveButton.setText("Save Game.ini")
        self.settingsSaveButton.setEnabled(False)

        self.settingsPageTextEditors.setCurrentIndex(1)

        global install_path
        install_path = self.arkInstallInput.text().strip()

        if self.__check_valid_path_inputs(check_steam_cmd=False, settings_editor=True):
            game_settings_path = os.path.join(install_path, "ShooterGame", "Saved", "Config", "WindowsServer", "Game.ini")

            if os.path.isfile(game_settings_path):
                try:
                    with open(game_settings_path, "r", encoding="utf-8") as f:
                        self.settingsTextEditor.setText(f.read())
                        self.settingsSaveButton.setEnabled(True)
                except Exception as e:
                    self.append_output(f"Error reading Game.ini: {e}", settings_editor=True)
            else:
                # Fall back to the template file
                if os.path.isfile(template_path):
                    try:
                        with open(template_path, "r", encoding="utf-8") as f:
                            self.settingsTextEditor.setText(f.read())
                            self.settingsSaveButton.setEnabled(True)
                    except Exception as e:
                        self.append_output(f"Error reading template Game.ini at {template_path}: {e}", settings_editor=True)
                else:
                    self.append_output(f"Game.ini not found and no template available at {template_path}.", settings_editor=True)


    def save_settings(self, game_user_settings=True):
        global install_path
        install_path = self.arkInstallInput.text().strip()
        if game_user_settings:
            # Save GameUserSettings.ini
            if self.__check_valid_path_inputs(check_steam_cmd=False, settings_editor=True):
                user_settings_path = os.path.join(install_path, "ShooterGame", "Saved", "Config", "WindowsServer")
                if os.path.exists(user_settings_path):
                    file_path = os.path.join(user_settings_path, "GameUserSettings.ini")
                    try:
                        with open(file_path, "w", encoding="utf-8") as f:
                            f.write(self.userSettingsTextEditor.toPlainText())
                            self.indicate_save_success()
                    except Exception as e:
                        self.append_output(f";Error when attempting save: {e}", settings_editor=True)
                else:
                    self.append_output(f";Error when traversing path to settings files with path set to: {user_settings_path}")
        else:
            # Save Game.ini
            if self.__check_valid_path_inputs(check_steam_cmd=False, settings_editor=True):
                settings_path = os.path.join(install_path, "ShooterGame", "Saved", "Config", "WindowsServer")
                if os.path.exists(settings_path):
                    file_path = os.path.join(settings_path, "Game.ini")
                    try:
                        with open(file_path, "w", encoding="utf-8") as f:
                            f.write(self.settingsTextEditor.toPlainText())
                            self.indicate_save_success()
                    except Exception as e:
                        self.append_output(f";Error when attempting save: {e}", settings_editor=True)
                else:
                    self.append_output(
                        f";Error when traversing path to settings files with path set to: {settings_path}")

    def indicate_save_success(self):
        self.settingsSaveButton.setText("Saved!")
        self.settingsSaveButton.setStyleSheet("background-color: lightgreen;")
        def reset_button():
            self.settingsSaveButton.setStyleSheet("")
            if self.onGameUserSettings:
                self.settingsSaveButton.setText("Save GameUserSettings.ini")
            else:
                self.settingsSaveButton.setText("Save Game.ini")

        QTimer.singleShot(1500, lambda: reset_button())


    def open_server_settings_page(self):
        self.switch_to_game_user_settings()
        self.stacked_widget.setCurrentIndex(1)

    def open_run_server_page(self):
        self.stacked_widget.setCurrentIndex(0)

    def open_directory(self, steam_cmd=False):
        if self.__check_valid_path_inputs(check_steam_cmd=steam_cmd, check_ark_install=(not steam_cmd), settings_editor=False):
            if steam_cmd:
                path = self.steamCmdInput.text().strip()
            else:
                path = self.arkInstallInput.text().strip()

            if os.path.exists(path):
                path = os.path.abspath(path)

                if platform.system() == "Windows": # Windows
                    os.startfile(path)
                elif platform.system() == "Darwin": # macOS
                    subprocess.run(["open", path])
                else: # Linux, etc.
                    subprocess.run(["xdg-open", path])
            else:
                self.append_output("Path does not exist, so cannot open to it.")

    def append_output(self, text, settings_editor=False):
        if not settings_editor:
            self.textEditor.append(text.strip())
        else:
            if self.onGameUserSettings:
                self.userSettingsTextEditor.append(text.strip())
            else:
                self.settingsTextEditor.append(text.strip())

    def create_start_bat_content(self):
        server_exe_path = os.path.join(install_path, "ShooterGame", "Binaries", "Win64", "ArkAscendedServer.exe")
        global start_bat_content
        start_bat_content = f'"{server_exe_path}" TheIsland_WP?listen?SessionName={self.serverNameInput.text().strip()}?ServerAdminPassword={self.serverAdminPasswordInput.text().strip()}?ServerPassword={self.serverPasswordInput.text().strip()}?Port={self.serverPortInput.text().strip()}?QueryPort={self.serverQueryPortInput.text().strip()}?MaxPlayers={self.serverMaxPlayersInput.text().strip()} -server -log {self.serverLaunchOptionsInput.text().strip()}'

    def __check_valid_path_inputs(self, check_steam_cmd=True, check_ark_install=True, settings_editor=False):
        if check_steam_cmd:
            if not self.steamCmdInput.text().strip():
                self.append_output("Include the location for SteamCMD or where you want it installed!", settings_editor=settings_editor)
                return False

        if check_ark_install:
            if not self.arkInstallInput.text().strip():
                self.append_output("Include the location for the ARK Server installation or where you want it installed!", settings_editor=settings_editor)
                return False

        return True

    def __check_valid_start_bat_inputs(self):
        if not self.serverNameInput.text().strip():
            self.append_output("Include the name of the server!")
            return False

        if not self.serverAdminPasswordInput.text().strip():
            self.append_output("Include the admin password of the server!")
            return False

        if not self.serverPortInput.text().strip():
            self.append_output("Include the port number of the server!")
            return False

        if not self.serverQueryPortInput.text().strip():
            self.append_output("Include the query port number of the server!")
            return False

        if not self.serverMaxPlayersInput.text().strip():
            self.append_output("Include the max players allowed in the server!")
            return False

        if not self.serverLaunchOptionsInput.text().strip():
            self.append_output("No launch options added.")
        return True

    def __save_user_prefs(self):
        user_prefs_success = False
        try:
            os.mkdir("data")
            self.append_output("Directory 'data' created.")
            user_prefs_success = True
        except FileExistsError:
            self.append_output("Directory 'data' already exists.")
            user_prefs_success = True
        except OSError as e:
            self.append_output(f"Error creating 'data' directory: {e}")

        if user_prefs_success:
            with open("data/user.prefs", "w", encoding="utf-8") as f:
                f.write(
                    f"""-SteamCMD: {self.steamCmdInput.text().strip()}
-ArkServerInstall: {self.arkInstallInput.text().strip()}
-ServerName: {self.serverNameInput.text().strip()}
-ServerAdminPassword: {self.serverAdminPasswordInput.text().strip()}
-ServerPassword: {self.serverPasswordInput.text().strip()}
-ServerPort: {self.serverPortInput.text().strip()}
-ServerQueryPort: {self.serverQueryPortInput.text().strip()}
-ServerMaxPlayers: {self.serverMaxPlayersInput.text().strip()}
-ServerLaunchOptions: {self.serverLaunchOptionsInput.text().strip()}"""
                )

    def __load_user_prefs(self):
        if os.path.exists("data/user.prefs"):
            self.append_output("Loading user preferences.")
            with open("data/user.prefs", "r", encoding="utf-8") as f:
                for line in f:
                    if len(line.strip().split()) > 1:
                        if "-SteamCMD" in line.strip():
                            self.steamCmdInput.setText(line.strip().split()[1])
                        if "-ArkServerInstall" in line.strip():
                            self.arkInstallInput.setText(line.strip().split()[1])
                        if "-ServerName" in line.strip():
                            self.serverNameInput.setText(line.strip().split()[1])
                        if "-ServerAdminPassword" in line.strip():
                            self.serverAdminPasswordInput.setText(line.strip().split()[1])
                        if "-ServerPassword" in line.strip():
                            self.serverPasswordInput.setText(line.strip().split()[1])
                        if "-ServerPort" in line.strip():
                            self.serverPortInput.setText(line.strip().split()[1])
                        if "-ServerQueryPort" in line.strip():
                            self.serverQueryPortInput.setText(line.strip().split()[1])
                        if "-ServerMaxPlayers" in line.strip():
                            self.serverMaxPlayersInput.setText(line.strip().split()[1])
                        if "-ServerLaunchOptions" in line.strip():
                            self.serverLaunchOptionsInput.setText(line.strip().split()[1])
        else:
            self.append_output("No user preferences set.")

    def setup_server_run_widget(self):
        server_layout = QVBoxLayout()

        server_layout.addWidget(QLabel("SteamCMD Path:"))
        server_layout.addLayout(self.steamCmdLayout)

        server_layout.addWidget(QLabel("ARK Server Install Path:"))
        server_layout.addLayout(self.arkInstallLayout)

        server_layout.addWidget(QLabel("Server Name"))
        server_layout.addWidget(self.serverNameInput)

        server_layout.addWidget(QLabel("Admin Password"))
        server_layout.addWidget(self.serverAdminPasswordInput)

        server_layout.addWidget(QLabel("Server Password"))
        server_layout.addWidget(self.serverPasswordInput)

        server_layout.addWidget(QLabel("Port"))
        server_layout.addWidget(self.serverPortInput)

        server_layout.addWidget(QLabel("Query Port"))
        server_layout.addWidget(self.serverQueryPortInput)

        server_layout.addWidget(QLabel("Max Players"))
        server_layout.addWidget(self.serverMaxPlayersInput)

        server_layout.addWidget(QLabel("Launch Options"))
        server_layout.addWidget(self.serverLaunchOptionsInput)

        server_layout.addWidget(self.runButton)
        server_layout.addWidget(self.startServerButton)
        server_layout.addWidget(self.serverSettingsPageButton)

        server_layout.addWidget(self.textEditor)

        self.server_widget.setLayout(server_layout)

    def setup_server_settings_widget(self):
        settings_layout = QVBoxLayout()

        settings_layout.addWidget(self.settingsFileControlPanel)

        settings_layout.addWidget(self.settingsPageTextEditors)
        settings_layout.addWidget(self.settingsSaveButton)
        settings_layout.addWidget(self.serverRunPageButton)

        self.settings_widget.setLayout(settings_layout)


if __name__ == "__main__":
    app = QApplication([])
    window = ArkManager()
    window.show()
    app.exec_()
