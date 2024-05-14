import os
import random
import string
from enum import Enum
import logging

import click
import json
from rich import console
from rich.prompt import Prompt
from rich.text import Text
from rich.padding import Padding
from dotenv import load_dotenv
from langchain.chains.graph_qa.cypher import GraphCypherQAChain
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_community.graphs import Neo4jGraph
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_openai import ChatOpenAI

from langchain_core.tracers.base import logger as tracer_logger

from utils.response_handler import ResponseHandlerFactory, ResponseTypes


# supress warnings from that logger
tracer_logger.setLevel(logging.ERROR)

load_dotenv()

NEO4J_URL = os.getenv("NEO4J_URL")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
      
Console = console.Console()

_SESSION_STORE = {}


class Model(str, Enum):
    """The model to use for the language model."""

    GPT4_Turbo = "gpt-4-turbo"
    GPT4 = "gpt-4"
    GPT3_5_Turbo = "gpt-3.5-turbo"
    GPT3_5 = "gpt-3.5"


def generate_session_id(length: int = 6) -> str:
    """Generates a random session ID.

    Args:
        length (int, optional): The length of the session ID. Defaults to 6.

    Returns:
        str: The session ID.
    """
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


def create_neo4j_graph(
    url: str = NEO4J_URL,
    user: str = NEO4J_USER,
    password: str = NEO4J_PASSWORD,
    timeout: int = 30,
    sanitize: bool = False,  # no sanitization for the sandbox environment,
    **kwargs,
) -> Neo4jGraph:
    """Creates a Neo4jGraph instance that connects to the Neo4j database.

    Args:
        url (str, optional): The URL of the Neo4j database. Defaults to NEO4J_URL.
        user (str, optional): The username of the Neo4j database. Defaults to NEO4J_USER.
        password (str, optional): The password of the Neo4j database. Defaults to NEO4J_PASSWORD.
        timeout (int, optional): The timeout in seconds for the connection. Defaults to 30.
        sanitize (bool, optional): Whether to sanitize the Cypher queries. Defaults to False.
        **kwargs: Additional keyword arguments to pass to the Neo4jGraph constructor.

    Returns:
        Neo4jGraph: The Neo4jGraph instance.
    """
    return Neo4jGraph(
        url=url,
        username=user,
        password=password,
        timeout=timeout,
        sanitize=sanitize,
        **kwargs,
    )


def create_cypher_chain(
    graph: Neo4jGraph,
    model: str,
    temperature: float = 0,
    verbose: bool = False,
    validate_cypher: bool = True,
) -> GraphCypherQAChain:
    """Creates a GraphCypherQAChain instance with the specified graph and language model.

    Args:
        graph (Neo4jGraph): The Neo4jGraph instance.
        model (str): The model to use for the language model.
        temperature (float, optional): The temperature to use for the language model. Defaults to 0.
        verbose (bool, optional): Whether to enable verbose mode. Defaults to False.
        validate_cypher (bool, optional): Whether to validate the Cypher queries. Defaults to True.

    Returns:
        GraphCypherQAChain: The GraphCypherQAChain instance.
    """
    return GraphCypherQAChain.from_llm(
        graph=graph,
        cypher_llm=ChatOpenAI(temperature=temperature, model=model),
        qa_llm=ChatOpenAI(temperature=temperature, model=model),
        validate_cypher=validate_cypher,
        verbose=verbose,
    )


def load_system_prompt_template(path: str = "prompts/system.md") -> ChatPromptTemplate:
    """Loads the system prompt using the contents in the specified file.

    Args:
        path (str, optional): The path to the Markdown file. Defaults to "prompts/system.md".

    Returns:
        ChatPromptTemplate: The system prompt template, with two placeholders for the {{history}} and the {{question}},
        respectively.
    """
    with open(path, "r") as file:
        prompt_content = file.read()

    return ChatPromptTemplate.from_messages(
        [
            ("system", prompt_content),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{question}"),
        ]
    )


def get_session_history(session_id: str) -> BaseChatMessageHistory:
    """Get a cached ChatMessageHistory instance for the given session ID, or create a new one if it does not exist.

    Args:
        session_id (str): unique identifier for the session.

    Returns:
        BaseChatMessageHistory: The ChatMessageHistory instance.
    """
    global _SESSION_STORE

    if session_id not in _SESSION_STORE:
        _SESSION_STORE[session_id] = ChatMessageHistory()
    return _SESSION_STORE[session_id]



@click.command()
@click.option(
    "--model",
    type=click.Choice([model.value for model in Model]),
    default=Model.GPT4_Turbo,
    help="The model to use for the assistant LLM.",
)
@click.option("--debug", is_flag=True, help="Whether to enable debug mode.")
@click.option(
    "--temperature",
    type=float,
    default=0.0,
    help="The temperature to use for the language model. Higher values result in more diverse responses.",
)
@click.option(
    "--dump-memory-on-exit",
    is_flag=True,
    help="Whether to dump the memory to a file on exit.",
)
def main(
    model: str = Model.GPT4_Turbo.value,
    debug: bool = False,
    temperature: float = 0,
    dump_memory_on_exit: bool = False,
):
    """The main function that runs the assistant.

    Args:

        model (str, optional): The model to use for the assistant LLM. Defaults to Model.GPT4_Turbo.value.
        debug (bool, optional): Whether to enable debug mode. Defaults to False.
        temperature (float, optional): The temperature to use for the language model. Defaults to 0.
        dump_memory_on_exit (bool, optional): Whether to dump the memory to a JSON file on exit. Defaults to False.
    """

    graph = create_neo4j_graph()
    system_prompt = load_system_prompt_template()

    # the chain that handles Neo4j queries
    cypher_chain = create_cypher_chain(graph, model, temperature=temperature, verbose=debug)

    # TODO: there's probably a way to speed this up doing a single call to the QA LLM loaded as part of the Cypher chain
    llm = ChatOpenAI(temperature=temperature, model=model)

    chain_with_history = RunnableWithMessageHistory(
        # creates a chain
        system_prompt | llm,
        get_session_history,
        input_messages_key="question",
        history_messages_key="history",
    )

    session_id = generate_session_id()
    config = {"configurable": {"session_id": session_id}}

    try:
        assistant_name = f"Assistant({model})"
        greeting = Text(f"{assistant_name}: Hey! I'm your personal movie assistant, how can I help you? (to exit, press Ctrl+C)")
        greeting.stylize("bold green", 0, 9)
        greeting = Padding(greeting, (0, 0))

        Console.print(greeting)
        Console.print(
            Padding("(feel free to give me feedback whenever the responses don't meet your expectations!)", (0, 0, 1, 0))
        )
        user_prompt = Text("You", style="bold blue")

        # an infinite loop to keep the assistant running until the user exits
        while True:
            user_query = Prompt.ask(user_prompt)
            query_classification_res = chain_with_history.invoke(
                {"question": "Classify query:" + user_query}, config=config
            )

            try:
                response_handler = ResponseHandlerFactory.create_response_handler(
                    ResponseTypes(query_classification_res.content[0])
                )
            except ValueError:
                # if the query is not classified, default to invalid query
                response_handler = ResponseHandlerFactory.create_response_handler(
                    ResponseTypes.INVALID
                )
            
            if response_handler.type_ == ResponseTypes.QUERY:
                try:
                    # include past history in the context
                    additional_info = query_classification_res.content[3:] if len(query_classification_res.content) > 3 else ""
                    db_response = cypher_chain.invoke(additional_info + " " + user_query)
                except Exception as e:
                    db_response = {"result": "I'm sorry, I couldn't find any results."}
                
                context = response_handler.get_context(db_response)
            else:
                context = response_handler.get_context()

            user_query_response = chain_with_history.invoke(
                {
                    "question": context
                    + "Using the context, respond to following query (remember to incorporate any and all past feedback):"
                    + user_query
                },
                config=config,
            )

            response = Text(f"{assistant_name}:" + user_query_response.content)
            response.stylize("bold green", 0, 9)
            response = Padding(response, (1, 0))
            Console.print(response)

    except KeyboardInterrupt as e:
        outro_text = Text("Leaving so soon? See ya next time!", style="bold green")
        Console.print(Padding(outro_text, (1, 0)))

        if dump_memory_on_exit:
            with open(f"memory-{session_id}.json", "w") as f:
                data = json.dump(
                    json.loads(_SESSION_STORE[session_id].json()), f, indent=2
                )


if __name__ == "__main__":
    main()
