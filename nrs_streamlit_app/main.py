import streamlit as st

def main():
    st.set_page_config(
        page_title="My Streamlit App",
        page_icon="📊",
        layout="centered"
    )

    st.title("Welcome to My Streamlit App")
    st.write("This is a basic Streamlit application.")

    name = st.text_input("Enter your name")

    if st.button("Submit"):
        if name:
            st.success(f"Hello, {name}! 👋")
        else:
            st.warning("Please enter your name.")

if __name__ == "__main__":
    main()
