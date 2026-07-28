from components.agents import build_search_agent, build_reader_agent, writer_chain, critic_chain

def pipeline(topic : str) -> dict :   # this dict is nothing but the state that will be passed from agent to agent
    state = {}


    print("\n"+" ="*50)
    print("Step 1 - search agent is working ...")
    print("="*50)

    # search agent
    search_agent = build_search_agent()
    search_result = search_agent.invoke({"messages" : [{"role": "user","content": f"Find recent, reliable and detailed information about: {topic}"}]})
    state["search_results"] = search_result["messages"][-1].content

    print(f"\n Search Result : \n {state['search_results']}")



    print("\n"+" ="*50)
    print("Step 2 - Reader agent is scraping top resources ...")
    print("="*50)

    #step 2 - reader agent 
    reader_agent = build_reader_agent()
    reader_result = reader_agent.invoke({"messages": [{"role" : "user","content" :
                                                                                    f"""Based on the following search results about '{topic}',
                                                                                    pick the most relevant URL and scrape it for deeper content.\n\n"
                                                                                    Search Results:\n{state['search_results'][:800]}"""
                                                        }]
                                                            })

    state["scraped_content"] = reader_result['messages'][-1].content

    print(f"\nscraped content : \n {state['scraped_content']}")



    print("\n"+" ="*50)
    print("Step 3 - Writer is drafting the report ...")
    print("="*50)

    # step 3 - writer chain
    combined_research = f"""
                            ### Search Results
                            {state["search_results"]}

                            ### Scraped Content
                            {state["scraped_content"]}
                            """

    report = writer_chain.invoke({"topic" : topic, "research" : combined_research})

    state["report"] = report

    print(f"\n Report : \n {state['report']}")


    print("\n"+" ="*50)
    print("Step 4 - Critic is analyzing the report ...")
    print("="*50)

    # critic chain

    feedback = critic_chain.invoke({
        "report" : state["report"]
    })

    state["feedback"] = feedback

    print(f"\n Feedback : \n {state['feedback']}")


    return state

if __name__ == "__main__":
    topic = input("\n Enter the research Topic : ")
    pipeline(topic)



