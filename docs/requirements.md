# What do I want?

At the heart of it, it's a text editor. A simple, zen like editor that allows me to focus on stuff I write as I write. The rest of the application is a management tool that will help me keep track of the book and organize everything.

## Markers

I can place markers anywhere in the text. Kind of like google docs.

1. Todo markers.
2. Edit markers.
3. Comment markers.

## Agents

I would like to request tasks from agents to do. They start the tasks and come back to me when they are completed.

## Tools

1. Spell Check and Grammar: Full Text/Selection.
2. Custom Edit job: Full Text/Selection (Give an instruction and it comes back with a list of edits. I apply the edits one by one, or apply-all)
3. Editorial Review: Full Text/Selection.
4. Custom Analysis: Full Text / Selection.

## Novel Structure

1. Sequence of Scenes: This is a kind of graph. The relationships are directional and sequential, but also loose. A graph visualizer here would be ideal.
2. Scene : The beating heart of the novel. The unit. It has a time, a place, and a previous scene and a next scene. It could belong to a chapter, it could belong to a part. But only one at a time. If it belongs to a chapter, it cannot directly belong to a part as the chapter is part of the part. Scenes can also loosely belong to other scenes. Perhaps not, previous or next, but definitely after or definitely before or somewhere around another scene.
3. Chapter : The structural element. Contains one or more scenes. This will be compiled from the scenes and database metadata.
4. Part : Structural container: Contains chapters, scenes, notes. 
5. Notes: Every element from scene to part to chapter can have notes. These notes can be tasks or questions or just observations. Every note is a conversation. Agents can reply or I can reply as the thought expands.
6. Dependencies: A scene can have dependency on the events on another scenes.

## Metadata manager

1. Master name list / Directory of who's who.
2. Event list
3. Character Sheet: Personality and History.
4. Story summary / Scene summary

## UI Features

1. The editor: A rich markdown editor. Should allow grammarly.
2. Scene graph analyzer: I can see the relationships between the scenes.
3. HomePage
   1. Bookshelf
      1. Title + Cover art (if uploaded)
      2. Add new title
         1. Title
         2. Path to save the files in.
      3. Clicking a book takes you to the book home.
4. Book Home
   1. Left navigation:
      1. Graph View: Show the scenes as the graph. Use D3 js to show the scenes as nodes. Zoom in zoom out.
      2. Outline View: Show the scenes as a tabular layout. Each scene is a card with title, description and other columns that I can add/remove from the scenes property list.
      3. Clicking on a scene opens the editor.
   2. Scene editor
      1. Center (main body): Rich Markdown editor.
      2. Top Panel: Above rich editor toolbar
         1. Relationships: This button opens a popup that shows the scene relationship to others. Previous, Next are hard relationships. Definitely after, Definitely before are softer relationships. Author can update the relationships from here. Relationship-type --> Dropdown of scenes in sequence.
         2. Metadata: This button opens the meta-data related to this scene. The part / or chapter it belongs to (both are optional). The characters, the date/time, where it is happening, the summary, the mood, the arc of the scene, the emotional trajectory.
         3. Dependencies: This button shows the list of scenes that this scene depends on and why. The author can add a dependency manually.
      3. Right panel: Accordian collapsed pane with the following info for the scenes
         1. Notes/Comments: Any snippets or text that the author wants to add will show here.
         2. Tasks/Todos: Any tasks or todo that the author decides will show up here.
         3. Agent Jobs: Any task for AI agents that was created will be shown here.

## Data Stuff (Json DB / Low DB / RxDB)

1. Scenes will be kept on the folder as markdown files.
2. Chapters will be compiled from the Scenes and placed in folders named by parts.
3. Database
   1. Book
      1. Title
      2. Cover-image-path
      3. FolderPath
   2. Chapter (Part of the chapterization)
      1. Title
      2. PreviousChapter
      3. NextChapter
      4. PartId
   3. Part (Part of the chapterization)
      1. Title
      2. PreviousPartId
      3. NextPartId
      4. BookId
   4. Plotline
      1. Title
      2. Description
   5. Character
   6. Scene_character
      1. SceneId
      2. CharacterId
   7. Scene_plotline
      1. SceneId
      2. PlotLineId
   8. Notes
      1. SceneId
      2. Note (large text)
   9. Todo
      1. SceneId
      2. Action
      3. Progress
      4. Status
   10. Scene
       1. Title
       2. Location (in story)
       3. DateTime (in story)
       4. PreviousSceneId (nullable)
       5. NextSceneId (nullable)
       6. PartId (nullable)
       7. ChapterId (nullable)
       8. Description (text)
       9. Mood (text)
       10. Emotional Arc (text)
       11. Summary (text)

## How things flow (User stories and flow)

1. I open the app and it shows me the home page. There are titles there. That data will come from a database that is maintained at the app root level.
2. I will click on a book.
3. It will then show me the book home page.
4. The data for the book home will come from the database kept in the book's folder path. It will not be saved in the app root level. This way I can separate the data for each book.
5. I have a list of scenes that I can access view graph view or list view.
6. In both views, I should be able to add a new scene, decide optionally where in the sequence it lies, or at least I can enter definitely after or definitely before if I don't know the exact placement yet. Chapter, part... all that is optional. Title and description is not. I know what that scene does. I should also be able to enter the mood, emotional arc.
7. In graph view the scenes connected via previous_scene_id and next_scene_id are shown with solid lines in sequence. The ones that are fuzzy with definitely before and definitely after are shown with thin dotted lines. In graph view, just the title is shown. I can hover to see the full description.
8. In table view the scenes are shown in sequence, and there is a button to show all scenes that are not yet firmly assigned a sequence.
9. When I click the scene, I should be able to see a rich text editor that helps me write in markdown format.
10. In the middle of writing, if I have a question, I can select a line, or simply click the chat button and it'll open a chat window. I ask the AI agent to do something, or answer a question, or research something etc. This will be saved in the right panel in the accordian pane.
11. In the middle of writing, I can add a comment or create a todo for myself.
12. In the middle of writing, I can have the AI update the metadata of the scene
    1. Update the characters that appear in the scene.
    2. Update the summary of the scene.
13. The AI window should be configurable, and I should be able to choose the models that I want.
    1. There will be a settings page in the app where I can enter the API keys. These will be put in the APP level root db.
    2. I should be able to enter models that I want.
    3. I should be able to create common 'AI-Jobs' like 'check-grammar' or 'editorial-review' and I should be able to enter a custom prompt for these. These will be saved and I'll have them available in the top menu on the scene editor page as a drop-down. Selecting these will trigger an AI-job that will be run just as a chat and will be accessible via the right side accordian. All AI-jobs are also chats. So when I click a common-job, it opens the chat, picks the default model for that ai-job and starts the conversation.
    4. AI will have access to the backend API and will be able to add todos, update summaries or metadata while chatting.

