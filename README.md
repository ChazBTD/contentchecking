**Note: we included a systems diagram detailing the proccesing layers of our app, move the media slides to read**

## Inspiration
As remote work increases, staying on task during work hours is getting harder with the availability of media and entertainment. This burden is oftentimes placed on team leaders. We believe that managers and leaders should be setting the direction for the team, not spending time micromanaging individuals. This is why we decided to implement Claude AI as a detection, decision, and flagging system to help HR and managers keep teams accountable at the click of a button while maintaining the group aspect of accountability.

## What it does
The extension allows company leaders or HR managers to "warn" or "block" certain websites that team members are using on their computers during work hours. We built an extension that extracts an active link of the employee's browser feed it to AI to check whether or not that link is work-related. The backend caches repeated links so generative tokens are not wastedd. Each team member ID is also attatched to their specific role so the AI evaluates content based on the context of what their jobs is.

## How we built it (stack)
Backend: Firebase/Firestore to store team status and content being flagged
Frontend (UI for manager): Streamlit to show the real-time manager dashboard that gives the team status, includes a window to resolve tickets of specific members, and update settings like the block list.
Frontend (Browser extension for team members): Checks if the browser URL active on the member's work desktop and sends it to backend. When managers resolve tickets, it is updated on the member's side through website blocking, warning signals , etc.
Generative component: Claude Sonnet 4 determines if the content of the website or video (title, descriptions, author, etc.) is related or appropriate for the role of each team member. The prompt and token production is optimized for speed to update every 10 seconds.

## Challenges we ran into
We ran into the problem of the AI tool being too harsh on deciding if something was work-related or not. For exapmle, websites such as forums (reddit, even stack overflow) active to solve code issues where flagged as "not work" on a software engineer's computer and sent to the manager's even though it could be helping them complete work. The core issue was in the scoring and evaluation mechanism that the Claude language modelled using the system prompt, we iterated through the system prompt multiple times to ensure it was able to get most test cases right, and we plan to continue tuning giving examples to the system prompt so it can resolve edge cases as well.

## Accomplishments that we're proud of
We exposed ourselves to new frameworks that we weren't used to, like connecting extensions to a real-time database, and posting chatbot logical decisions to the manager, all within the refresh time. We had to do a lot of manual testing and documentation reading, and we are very proud of the fact that this platform-extension connection is functional, consistent, and even scalable for more members, managing parties, and features in the future.

## What we learned
We learned how to navigate frontend and backend through a database when information and the flag boolean are constantly being changed across different employees. We had to sync many pieces of data at the same time and timestamp individual components to alleviate the network. We also had to manage many different project tokens because compatibility of different components in the stack.

## What's next for TaskForce
- friend and family accountability with parents having admin
- training data to evaluate what counts as work/not work 
- integrating more extension capabilities to help the team member address their concerns with their work as well
