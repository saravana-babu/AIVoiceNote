# VoiceMind AI - Developer Documentation

Welcome to the development documentation for **VoiceMind AI**, a cross-platform AI Voice Notes application built using a Turborepo monorepo structure.

---

## 1. Project Architecture

This repository is structured as a monorepo containing a mobile app client, several shared TypeScript utility packages, and a FastAPI backend.

```
voicemind-ai/
├── apps/
│   └── mobile/                # React Native / Expo application
├── packages/
│   ├── shared/                # Common types, utilities, and constants
│   ├── ui/                    # Reusable React Native UI components
│   ├── audio/                 # Audio recording and playback hooks
│   ├── storage/               # Key-value storage abstraction layer
│   └── api/                   # API client for backend communication
├── backend/
│   ├── main.py                # FastAPI app endpoints
│   └── pyproject.toml         # Python project configuration
├── package.json               # Root monorepo workspace package file
└── turbo.json                 # Turborepo task runner configuration
```

---

## 2. Prerequisites

Ensure you have the following installed on your system:

- **Node.js** (v22 or later) and **npm** (v11 or later)
- **Python** (v3.12 or later)
- **`uv`** (extremely fast Python package manager)
- **Git**

---

## 3. Setup & Installation

### Step 1: Install Node.js Dependencies

From the root of the project, run:

```bash
npm install
```

This will set up workspaces, link internal packages (`@voicemind/ui`, `@voicemind/shared`, etc.), and initialize Git hooks using Husky.

### Step 2: Set Up Python Backend

From the root of the project, run:

```bash
cd backend
uv sync
```

This will automatically create a virtual environment (`.venv`) and install all required Python dependencies.

---

## 4. Development Commands

### Running in Development Mode

You can spin up all packages in watch mode using Turborepo from the root:

```bash
npm run dev
```

### Building the Packages & Apps

Build all workspaces from the root:

```bash
npm run build
```

### Linting and Formatting

To verify styling, linting, and formatting:

```bash
# Run linting check
npm run lint

# Check formatting
npm run format:check

# Fix formatting
npm run format
```

---

## 5. Running the Applications

### Starting the Backend

To start the FastAPI backend server manually:

```bash
cd backend
uv run uvicorn main:app --reload --port 8000
```

The backend API will be available at `http://localhost:8000`. You can inspect the interactive docs at `http://localhost:8000/docs`.

### Starting the Mobile Client (Expo)

To start the Expo bundler:

```bash
cd apps/mobile
npm run start
```

- Press `i` to open in the iOS Simulator.
- Press `a` to open in the Android Emulator.
- Press `w` to run the web version.

#### Cross-Platform Desktop Support (macOS & Windows)

To support desktop, we target:

1. **Web Wrapper (Electron/Tauri):** The Expo app compiles to a standard web build (`npm run web`), which can be bundled into a desktop wrapper.
2. **Native Bindings (React Native macOS & Windows):** Under the hood, you can run `npx expo prebuild` to eject native folders, and then add `react-native-windows` and `react-native-macos` dependencies to run natively on desktops.

---

## 6. Git Commit Guidelines

This project enforcesconventional commits. Make sure your commit messages follow this pattern:

```
<type>(<scope>): <subject>
```

**Common types:**

- `feat`: A new feature
- `fix`: A bug fix
- `docs`: Documentation changes
- `style`: Changes that do not affect the meaning of the code (white-space, formatting, etc.)
- `refactor`: A code change that neither fixes a bug nor adds a feature
- `test`: Adding missing tests or correcting existing tests
- `chore`: Changes to the build process or auxiliary tools/libraries

Example: `feat(audio): add useAudioRecorder hooks`
