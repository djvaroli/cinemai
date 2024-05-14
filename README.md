# CinemAI

## Overview
The follwoing repo contains an implementation for a LLM-based chatbot designed designed to respond to queries about movies using a Neo4j graph database. The assistant is implemented using LangChain, Neo4j, and OpenAI's GPT models to process queries, interact with the database, and generate responses. The assistant is also capable of accepting user feedback and using it to improve future responses.

## Features
- **Multiple Language Models**: Supports various GPT models (GPT-4, GPT-4 Turbo, GPT-3.5, GPT-3.5 Turbo). Can be customized using the `--model` flag.
- **Customizable Prompts**: Uses system prompt templates to define interaction flow. Must be customized manually in the `prompts` directory.
- **Memory Management**: Maintains a history of past messages. History can be saved to a JSON file upon termination of the chat using the `--dump-memory-on-exit` flag.
- **Debug Mode**: Provides verbose output for debugging purposes. Can be toggled using the `--debug` flag.
- Optional reporting to LangSmith for better insight into the workings of each chain. (Can be configured in the `.env` file)

## Approach
The assistant is comprised of several "chains":
* a chain that converts natural language queries into Cypher queries and then executes them against the Neo4j database.
* a chain that converts the results of the database queries into natural language responses.
* a chain that manages the decision-making process for how to respond to a given user query, handle feedback, and provide contextual information to the Cypher chain. Much of this is achieved via a classifcation mechanism that groups queries into 4 categories: `F - feedback`, `Q - query database`, `M - memory response`, and `I - invalid query`.


## Installation

1. **Clone the repository**:
    ```sh
    git clone <repository_url>
    cd <repository_directory>
    ```
2. **Create conda environment**:
    ```sh
    conda create -n cinemai python=3.10 -y
    conda activate cinemai
    ```

3. **Install dependencies**:
    ```sh
    pip install -r requirements.txt
    ```

4. **Set up environment variables**:
    Create a `.env` file in the root directory with the following content:
    ```env
    OPENAI_API_KEY=your_openai_api_key
    NEO4J_URL=bolt://localhost:7687
    NEO4J_PASSWORD=your_password
    # optional for langsmith reporting
    LANGCHAIN_API_KEY=your_langchain_api_key
    LANGCHAIN_TRACING_V2='true'
    ```
    also see the `.env.example` file for an example.

## Usage

### Running the Assistant
To start the assistant, run:
```sh
python cinemai.py --model gpt-4-turbo --debug --temperature 0.01
```

### Command-Line Options
* `--model`: Specifies the language model to use (default: gpt-4-turbo).
* `--debug`: Enables debug mode for verbose output.
* `--temperature`: Sets the temperature for the language model (default: 0.0).
* `--dump-memory-on-exit`: Dumps the session memory to a file upon exit. Defaults to `False`.


