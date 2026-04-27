# Sequential Thinking MCP Server

An MCP server implementation that provides a tool for dynamic and reflective problem-solving through concise, user-visible reasoning checkpoints.

This server is designed for clients that must not expose hidden chain-of-thought in tool calls or tool outputs. The tool accepts brief planning summaries, returns only progress metadata, and does not log raw checkpoint text unless explicitly configured to do so.

## Features

- Break down complex problems into manageable steps
- Revise and refine reasoning checkpoints as understanding deepens
- Branch into alternative paths of reasoning
- Adjust the total number of thoughts dynamically
- Generate and verify solution hypotheses
- Avoid returning raw reasoning text in tool output
- Avoid logging raw reasoning text by default

## Tool

### sequential_thinking

Facilitates a step-by-step planning process for problem-solving and analysis. Inputs should be concise summaries that are safe to show in client transcripts. Do not include hidden chain-of-thought, secrets, credentials, or security-sensitive operational details.

**Inputs:**
- `thought` (string): A concise, user-visible reasoning checkpoint
- `nextThoughtNeeded` (boolean): Whether another thought step is needed
- `thoughtNumber` (integer): Current thought number
- `totalThoughts` (integer): Estimated total thoughts needed
- `isRevision` (boolean, optional): Whether this revises previous thinking
- `revisesThought` (integer, optional): Which thought is being reconsidered
- `branchFromThought` (integer, optional): Branching point thought number
- `branchId` (string, optional): Branch identifier
- `needsMoreThoughts` (boolean, optional): If more thoughts are needed

## Usage

The Sequential Thinking tool is designed for:
- Breaking down complex problems into steps
- Planning and design with room for revision
- Analysis that might need course correction
- Problems where the full scope might not be clear initially
- Tasks that need to maintain context over multiple steps
- Situations where irrelevant information needs to be filtered out

In practice, you do not call `sequential_thinking` directly by hand unless your client exposes raw tool calls. Instead, connect the server to an MCP-aware host and ask the model to think through a problem step by step. The host can then decide to call the tool one or more times while it works.

### What it looks like in use

Example prompts that typically benefit from this tool:

- `Plan a database migration from PostgreSQL 14 to 16, list risks, and revise the plan if downtime exceeds 5 minutes.`
- `Debug why this deployment only fails in production and show your reasoning step by step.`
- `Compare three architecture options for a file sync engine and branch if one assumption turns out to be wrong.`

### How to tell it is working

If your host or inspector shows tool activity, you should see repeated calls to `sequential_thinking` with fields such as:

- `thought`
- `thoughtNumber`
- `totalThoughts`
- `nextThoughtNeeded`

When the reasoning changes course, you may also see revision or branching fields like `isRevision`, `revisesThought`, `branchFromThought`, or `branchId`.

### Quick manual verification

After installing the server in your MCP host:

1. Restart or reload the host so it reconnects to the server.
2. Confirm the `sequential_thinking` tool appears in the host's MCP tool list or inspector.
3. Ask the host to solve a non-trivial problem in a step-by-step way.
4. Verify that the host invokes the tool multiple times instead of returning a one-shot answer.

## Configuration

Raw thought logging is disabled by default. To opt in for local debugging, set `ENABLE_THOUGHT_LOGGING` to `true`.

The legacy `DISABLE_THOUGHT_LOGGING=true` setting is still honored and takes precedence over `ENABLE_THOUGHT_LOGGING=true`.

### Usage with Claude Desktop

Add this to your `claude_desktop_config.json`:

#### npx

```json
{
  "mcpServers": {
    "sequential-thinking": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-sequential-thinking"
      ],
      "env": {
        "DISABLE_THOUGHT_LOGGING": "true"
      }
    }
  }
}
```

On Windows, use `cmd /c` to launch `npx`:

```json
{
  "mcpServers": {
    "sequential-thinking": {
      "command": "cmd",
      "args": [
        "/c",
        "npx",
        "-y",
        "@modelcontextprotocol/server-sequential-thinking"
      ],
      "env": {
        "DISABLE_THOUGHT_LOGGING": "true"
      }
    }
  }
}
```

#### docker

```json
{
  "mcpServers": {
    "sequentialthinking": {
      "command": "docker",
      "args": [
        "run",
        "--rm",
        "-i",
        "-e",
        "DISABLE_THOUGHT_LOGGING=true",
        "mcp/sequentialthinking"
      ]
    }
  }
}
```

To enable logging of thought information for local debugging, set env var: `ENABLE_THOUGHT_LOGGING` to `true`.

### Usage with VS Code

For quick installation, click one of the installation buttons below...

[![Install with NPX in VS Code](https://img.shields.io/badge/VS_Code-NPM-0098FF?style=flat-square&logo=visualstudiocode&logoColor=white)](https://insiders.vscode.dev/redirect/mcp/install?name=sequentialthinking&config=%7B%22command%22%3A%22npx%22%2C%22args%22%3A%5B%22-y%22%2C%22%40modelcontextprotocol%2Fserver-sequential-thinking%22%5D%7D) [![Install with NPX in VS Code Insiders](https://img.shields.io/badge/VS_Code_Insiders-NPM-24bfa5?style=flat-square&logo=visualstudiocode&logoColor=white)](https://insiders.vscode.dev/redirect/mcp/install?name=sequentialthinking&config=%7B%22command%22%3A%22npx%22%2C%22args%22%3A%5B%22-y%22%2C%22%40modelcontextprotocol%2Fserver-sequential-thinking%22%5D%7D&quality=insiders)

[![Install with Docker in VS Code](https://img.shields.io/badge/VS_Code-Docker-0098FF?style=flat-square&logo=visualstudiocode&logoColor=white)](https://insiders.vscode.dev/redirect/mcp/install?name=sequentialthinking&config=%7B%22command%22%3A%22docker%22%2C%22args%22%3A%5B%22run%22%2C%22--rm%22%2C%22-i%22%2C%22mcp%2Fsequentialthinking%22%5D%7D) [![Install with Docker in VS Code Insiders](https://img.shields.io/badge/VS_Code_Insiders-Docker-24bfa5?style=flat-square&logo=visualstudiocode&logoColor=white)](https://insiders.vscode.dev/redirect/mcp/install?name=sequentialthinking&config=%7B%22command%22%3A%22docker%22%2C%22args%22%3A%5B%22run%22%2C%22--rm%22%2C%22-i%22%2C%22mcp%2Fsequentialthinking%22%5D%7D&quality=insiders)

For manual installation, you can configure the MCP server using one of these methods:

**Method 1: User Configuration (Recommended)**
Add the configuration to your user-level MCP configuration file. Open the Command Palette (`Ctrl + Shift + P`) and run `MCP: Open User Configuration`. This will open your user `mcp.json` file where you can add the server configuration.

**Method 2: Workspace Configuration**
Alternatively, you can add the configuration to a file called `.vscode/mcp.json` in your workspace. This will allow you to share the configuration with others.

> For more details about MCP configuration in VS Code, see the [official VS Code MCP documentation](https://code.visualstudio.com/docs/copilot/customization/mcp-servers).

For NPX installation:

```json
{
  "servers": {
    "sequential-thinking": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-sequential-thinking"
      ],
      "env": {
        "DISABLE_THOUGHT_LOGGING": "true"
      }
    }
  }
}
```

On Windows, use:

```json
{
  "servers": {
    "sequential-thinking": {
      "command": "cmd",
      "args": [
        "/c",
        "npx",
        "-y",
        "@modelcontextprotocol/server-sequential-thinking"
      ],
      "env": {
        "DISABLE_THOUGHT_LOGGING": "true"
      }
    }
  }
}
```

For Docker installation:

```json
{
  "servers": {
    "sequential-thinking": {
      "command": "docker",
      "args": [
        "run",
        "--rm",
        "-i",
        "-e",
        "DISABLE_THOUGHT_LOGGING=true",
        "mcp/sequentialthinking"
      ]
    }
  }
}
```

### Usage with Codex CLI

Run the following:

#### npx

```bash
codex mcp add sequential-thinking npx -y @modelcontextprotocol/server-sequential-thinking
```

## Building

Docker:

```bash
docker build -t mcp/sequentialthinking -f src/sequentialthinking/Dockerfile .
```

## License

This MCP server is licensed under the MIT License. This means you are free to use, modify, and distribute the software, subject to the terms and conditions of the MIT License. For more details, please see the LICENSE file in the project repository.
