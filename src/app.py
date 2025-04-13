import os
import warnings
import streamlit as st

# ------------------------------------------------
# Warning Filters (optional: suppress non-critical warnings)
# ------------------------------------------------
warnings.filterwarnings("ignore", message="Did not recognize type 'geometry'")
warnings.filterwarnings("ignore", message="Importing verbose from langchain root module is no longer supported")
warnings.filterwarnings("ignore", category=RuntimeWarning)

# ------------------------------------------------
# Page Configuration
# ------------------------------------------------
st.set_page_config(page_title="SQL Query Generator", layout="wide")

# ------------------------------------------------
# Custom CSS Styling
# ------------------------------------------------
custom_css = """
<style>
    /* Page background and font styling */
    body {
        background-color: #f4f6f9;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    
    /* Header styling */
    .main-title {
        font-size: 3rem;
        color: #2c3e50;
        text-align: center;
        margin-bottom: 0.5em;
        font-weight: 600;
    }
    
    .subheader {
        font-size: 1.5rem;
        color: #34495e;
    }
    
    /* Sidebar styling */
    .sidebar .sidebar-content {
        background-color: #ecf0f1;
        border-radius: 10px;
        padding: 1em;
    }
    
    /* Button styling */
    div.stButton > button {
        background-color: #3498db;
        color: white;
        border: none;
        border-radius: 5px;
        padding: 0.5em 1em;
        font-size: 1rem;
    }
    
    div.stButton > button:hover {
        background-color: #2980b9;
    }
    
    /* Code block styling */
    .stCodeBlock pre {
        background-color: #2d3436;
        color: #f4f4f4;
        border-radius: 5px;
        padding: 1em;
        font-size: 0.9rem;
    }
    
    /* Spinner styling (custom CSS override for spinners or messages) */
    .stSpinner {
        color: #3498db;
    }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# ------------------------------------------------
# Initialize session state for the database connection.
# ------------------------------------------------
if "db" not in st.session_state:
    st.session_state["db"] = None

# ------------------------------------------------
# Sidebar: Database Connection Details (Styled by default Streamlit theme + custom CSS applied above)
# ------------------------------------------------
st.sidebar.header("Database Connection Details")
host = st.sidebar.text_input("Host", value="localhost")
port = st.sidebar.text_input("Port", value="3306")
database = st.sidebar.text_input("Database Name", value="sakila")
username = st.sidebar.text_input("Username", value="root")
password = st.sidebar.text_input("Password", type="password", value="root")

if st.sidebar.button("Connect to Database"):
    try:
        db_uri = f"mysql+mysqlconnector://{username}:{password}@{host}:{port}/{database}"
        from langchain_community.utilities import SQLDatabase
        st.session_state["db"] = SQLDatabase.from_uri(db_uri)
        st.sidebar.success("Connected to database successfully!")
    except Exception as e:
        st.session_state["db"] = None
        st.sidebar.error(f"Failed to connect to database: {e}")

# ------------------------------------------------
# Ensure Google API Key is set.
# ------------------------------------------------
if "GOOGLE_API_KEY" not in os.environ:
    os.environ["GOOGLE_API_KEY"] = "YOUR_GEMINI_API_KEY"  # Replace with your valid key

# ------------------------------------------------
# Main Page Header and Description (With Custom Styles)
# ------------------------------------------------
st.markdown('<div class="main-title">SQL Query Generator</div>', unsafe_allow_html=True)
st.markdown('<p class="subheader" style="text-align: center;">Using LangChain & Google Generative AI</p>', unsafe_allow_html=True)
st.write("Enter a natural language question and get an SQL query to answer it.")

# ------------------------------------------------
# User Input: Natural Language Question
# ------------------------------------------------
user_question = st.text_input(
    "Enter your question", placeholder="e.g., What is the name of the actor with the most films?"
)

# ------------------------------------------------
# Step 1: SQL Query Generation
# ------------------------------------------------
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers.string import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_google_genai import ChatGoogleGenerativeAI

sql_template = """
You are an SQL generator. Given the following database schema and a natural language question,
provide only the SQL query that answers the question.
Use the table names exactly as provided in the schema.
For example, in the Sakila database, use 'actor' (not 'actors') and 'film_actor' for actor-film relationships.

{schema}

Question: {question}

Return only the SQL query with no additional explanation.
"""
sql_prompt = ChatPromptTemplate.from_template(sql_template)

llm = ChatGoogleGenerativeAI(
    api_key=os.getenv("GOOGLE_API_KEY"),
    model="gemini-1.5-pro"
)

def get_schema(_):
    if st.session_state.get("db") is None:
        return "No database connected."
    return st.session_state["db"].get_table_info()

def extract_sql(query_output: str) -> str:
    if "```sql" in query_output and "```" in query_output:
        extracted = query_output.split("```sql")[1].split("```")[0].strip()
    else:
        extracted = query_output.strip()
    # Replace common naming mismatches
    extracted = extracted.replace("FROM actors", "FROM actor")
    extracted = extracted.replace("JOIN roles", "JOIN film_actor")
    return extracted

sql_chain = (
    RunnablePassthrough.assign(schema=get_schema)
    | sql_prompt
    | llm.bind(stop=["\nSQL Result:"])
    | StrOutputParser()
)

# ------------------------------------------------
# Step 2: Optionally, Execute the SQL Query
# ------------------------------------------------
def run_generated_query(generated_sql: str):
    if st.session_state.get("db") is None:
        raise ValueError("No database connection.")
    return st.session_state["db"].run(generated_sql)

# ------------------------------------------------
# Full Execution: Generate (and optionally run) the SQL Query
# ------------------------------------------------
generated_sql = None

if st.button("Generate SQL Query"):
    if not user_question:
        st.warning("Please enter a question to generate an SQL query.")
    else:
        # Generate SQL query.
        with st.spinner("Generating SQL query..."):
            try:
                raw_output = sql_chain.invoke({"question": user_question})
                generated_sql = extract_sql(raw_output)
                st.success("SQL Query Generated!")
                st.code(generated_sql, language="sql")
            except Exception as e:
                st.error(f"Error generating SQL: {e}")
        
        # Optionally, execute the generated SQL query if a database connection exists.
        if generated_sql and st.session_state.get("db"):
            with st.spinner("Executing SQL query..."):
                try:
                    query_result = run_generated_query(generated_sql)
                    st.subheader("SQL Query Result:")
                    st.write(query_result)
                except Exception as e:
                    st.error(f"Error running query: {e}")
