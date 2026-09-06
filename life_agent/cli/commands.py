"""CLI command implementations."""

from datetime import date, datetime
from typing import Annotated, Optional

import typer
from rich.console import Console

from life_agent import __version__
from life_agent.config import get_settings
from life_agent.models.common import ActivityType, Priority, TaskCategory

console = Console()


def register_commands(app: typer.Typer) -> None:
    """Register all CLI commands on the given Typer app."""

    # ------------------------------------------------------------------
    # Foundation commands
    # ------------------------------------------------------------------

    @app.command("version")
    def version() -> None:
        """Show the application version."""
        console.print(f"personal-life-agent {__version__}")

    @app.command("health")
    def health() -> None:
        """Check that the application is running correctly."""
        settings = get_settings()
        console.print("[green]OK[/green] personal-life-agent is healthy")
        console.print(f"  environment: {settings.app_env}")
        console.print(f"  log level:   {settings.log_level}")

    @app.command("init")
    def init() -> None:
        """Initialise the local SQLite database."""
        from life_agent.db.database import init_db

        init_db()
        console.print("[green]Database initialised.[/green]")

    # ------------------------------------------------------------------
    # Task commands
    # ------------------------------------------------------------------

    @app.command("add-task")
    def add_task(
        title: str = typer.Argument(..., help="Short description of the task"),
        due: Annotated[Optional[str], typer.Option(help="Due date (YYYY-MM-DD)")] = None,
        priority: Annotated[Priority, typer.Option(help="low, medium, or high")] = Priority.MEDIUM,
        category: Annotated[TaskCategory, typer.Option(help="Task category")] = TaskCategory.OTHER,
    ) -> None:
        """Add a new task."""
        from life_agent.services.task_service import add_task as svc_add_task

        due_date: date | None = None
        if due is not None:
            try:
                due_date = date.fromisoformat(due)
            except ValueError:
                console.print(f"[red]Invalid date format:[/red] {due}  (expected YYYY-MM-DD)")
                raise typer.Exit(code=1)

        task = svc_add_task(
            title=title,
            due_date=due_date,
            priority=priority,
            category=category,
        )
        console.print(f"[green]Added task:[/green] {task.title}")

    @app.command("tasks")
    def tasks() -> None:
        """List all tasks."""
        from life_agent.cli.formatters import format_task_line
        from life_agent.services.task_service import get_all_tasks

        all_tasks = get_all_tasks()
        if not all_tasks:
            console.print("No tasks found.")
            return
        for i, task in enumerate(all_tasks, start=1):
            console.print(format_task_line(i, task))

    @app.command("done")
    def done(
        task_index: int = typer.Argument(..., help="Task number from the tasks list"),
    ) -> None:
        """Mark a task as done by its list number."""
        from life_agent.services.task_service import mark_task_done

        updated = mark_task_done(task_index)
        if updated is None:
            console.print(f"[red]No task found at index {task_index}.[/red]")
            raise typer.Exit(code=1)
        console.print(f"[green]Done:[/green] {updated.title}")

    # ------------------------------------------------------------------
    # Event commands
    # ------------------------------------------------------------------

    @app.command("add-event")
    def add_event(
        title: str = typer.Argument(..., help="Short description of the event"),
        start: str = typer.Option(..., help="Start time (YYYY-MM-DD HH:MM)"),
        location: Annotated[Optional[str], typer.Option(help="Location")] = None,
    ) -> None:
        """Add a new calendar event."""
        from life_agent.services.event_service import add_event as svc_add_event

        try:
            start_time = datetime.strptime(start, "%Y-%m-%d %H:%M")
        except ValueError:
            console.print(f"[red]Invalid datetime format:[/red] {start}  (expected YYYY-MM-DD HH:MM)")
            raise typer.Exit(code=1)

        event = svc_add_event(title=title, start_time=start_time, location=location)
        console.print(f"[green]Added event:[/green] {event.title}")

    @app.command("events")
    def events() -> None:
        """List all calendar events."""
        from life_agent.cli.formatters import format_event_line
        from life_agent.services.event_service import get_all_events

        all_events = get_all_events()
        if not all_events:
            console.print("No events found.")
            return
        for i, event in enumerate(all_events, start=1):
            console.print(format_event_line(i, event))

    # ------------------------------------------------------------------
    # Activity commands
    # ------------------------------------------------------------------

    @app.command("activity")
    def activity(
        title: str = typer.Argument(..., help="Short description of the activity"),
        activity_type: Annotated[ActivityType, typer.Option("--type", help="Activity type")] = ActivityType.OTHER,
        minutes: Annotated[Optional[int], typer.Option(help="Duration in minutes")] = None,
    ) -> None:
        """Log a new activity."""
        from life_agent.services.activity_service import add_activity as svc_add_activity

        logged = svc_add_activity(
            title=title,
            activity_type=activity_type,
            duration_minutes=minutes,
        )
        console.print(f"[green]Logged activity:[/green] {logged.title}")

    @app.command("activities")
    def activities() -> None:
        """List all logged activities."""
        from life_agent.cli.formatters import format_activity_line
        from life_agent.services.activity_service import get_all_activities

        all_activities = get_all_activities()
        if not all_activities:
            console.print("No activities found.")
            return
        for i, act in enumerate(all_activities, start=1):
            console.print(format_activity_line(i, act))

    # ------------------------------------------------------------------
    # Planner commands
    # ------------------------------------------------------------------

    @app.command("today")
    def today() -> None:
        """Show today's events, tasks due today, and other pending tasks."""
        from life_agent.cli.formatters import format_today_agenda
        from life_agent.services.planner_service import get_today_agenda

        console.print(format_today_agenda(get_today_agenda()))

    @app.command("week")
    def week() -> None:
        """Show events and task deadlines for the next 7 days."""
        from life_agent.cli.formatters import format_week_agenda
        from life_agent.services.planner_service import get_week_agenda

        console.print(format_week_agenda(get_week_agenda()))

    @app.command("deadlines")
    def deadlines() -> None:
        """Show pending tasks with due dates, sorted by date and priority."""
        from life_agent.cli.formatters import format_deadlines
        from life_agent.services.planner_service import get_upcoming_deadlines

        console.print(format_deadlines(get_upcoming_deadlines()))

    # ------------------------------------------------------------------
    # Reminder commands
    # ------------------------------------------------------------------

    @app.command("add-reminder")
    def add_reminder(
        title: str = typer.Argument(..., help="Short description of the reminder"),
        at: str = typer.Option(..., "--at", help="Remind at (YYYY-MM-DD HH:MM)"),
    ) -> None:
        """Add a new reminder."""
        from life_agent.services.reminder_service import add_reminder as svc_add_reminder

        try:
            remind_at = datetime.strptime(at, "%Y-%m-%d %H:%M")
        except ValueError:
            console.print(
                f"[red]Invalid datetime format:[/red] {at}  (expected YYYY-MM-DD HH:MM)"
            )
            raise typer.Exit(code=1)

        reminder = svc_add_reminder(title=title, remind_at=remind_at)
        console.print(
            f"[green]Added reminder #{reminder.id}:[/green] {reminder.title}"
        )

    @app.command("reminders")
    def reminders() -> None:
        """List pending reminders, sorted by remind_at ascending."""
        from life_agent.cli.formatters import format_reminder_line
        from life_agent.services.reminder_service import list_reminders as svc_list_reminders

        pending = svc_list_reminders()
        if not pending:
            console.print("No pending reminders.")
            return
        for reminder in pending:
            console.print(format_reminder_line(reminder))

    @app.command("dismiss-reminder")
    def dismiss_reminder(
        reminder_id: int = typer.Argument(..., help="Reminder database id (e.g. from `reminders`)"),
    ) -> None:
        """Mark a reminder as dismissed by its database id."""
        from life_agent.services.reminder_service import dismiss_reminder as svc_dismiss

        updated = svc_dismiss(reminder_id)
        if updated is None:
            console.print(f"[red]No reminder found with id {reminder_id}.[/red]")
            raise typer.Exit(code=1)
        console.print(f"[green]Dismissed reminder #{updated.id}:[/green] {updated.title}")

    # ------------------------------------------------------------------
    # Extraction command (read-only preview, no database writes)
    # ------------------------------------------------------------------

    @app.command("extract")
    def extract(
        text: str = typer.Argument(..., help="Unstructured note to extract"),
    ) -> None:
        """Extract structured items from natural language (preview only)."""
        from life_agent.cli.formatters import format_extraction_result
        from life_agent.services.extraction_service import extract_from_text

        if not text or not text.strip():
            console.print("[red]No text provided.[/red]")
            raise typer.Exit(code=1)

        result = extract_from_text(text)
        console.print(format_extraction_result(result))
        console.print()
        console.print(
            "[yellow]Nothing was saved. This is a read-only preview.[/yellow]"
        )

    @app.command("add")
    def add(
        text: str = typer.Argument(..., help="Natural language note to extract and save"),
        yes: Annotated[
            bool,
            typer.Option("--yes", "-y", help="Skip the prompt and save immediately"),
        ] = False,
    ) -> None:
        """Extract items from natural language and save them after confirmation."""
        from life_agent.agent.safety import is_affirmative
        from life_agent.cli.formatters import (
            format_confirmation_proposal,
            format_save_result,
        )
        from life_agent.services.confirmation_service import (
            build_confirmation_proposal,
            save_confirmed_extraction,
        )
        from life_agent.services.extraction_service import extract_from_text

        if not text or not text.strip():
            console.print("[red]No text provided.[/red]")
            raise typer.Exit(code=1)

        result = extract_from_text(text)
        proposal = build_confirmation_proposal(result)
        console.print(format_confirmation_proposal(proposal))
        console.print()

        if proposal.saveable_count == 0:
            console.print(
                "[yellow]Nothing to save. No items were stored.[/yellow]"
            )
            return

        if yes:
            confirmed = True
        else:
            answer = typer.prompt("Save this? [y/N]", default="", show_default=False)
            confirmed = is_affirmative(answer)

        if not confirmed:
            console.print("[yellow]Cancelled. Nothing was saved.[/yellow]")
            return

        save_result = save_confirmed_extraction(result, confirmed=True)
        console.print(format_save_result(save_result))

    @app.command("complete")
    def complete(
        text: str = typer.Argument(..., help="Natural language completion phrase"),
        yes: Annotated[
            bool,
            typer.Option("--yes", "-y", help="Skip the prompt and complete immediately"),
        ] = False,
    ) -> None:
        """Mark a planned activity as completed from natural language."""
        from life_agent.agent.safety import is_affirmative
        from life_agent.cli.formatters import format_completion_candidate
        from life_agent.services.completion_service import (
            complete_activity,
            find_completion_candidate,
            is_completion_phrase,
        )

        if not text or not text.strip():
            console.print("[red]No text provided.[/red]")
            raise typer.Exit(code=1)

        if not is_completion_phrase(text):
            console.print(
                "[yellow]That doesn't look like a completion phrase "
                "(e.g. \"Jag har tränat klart\").[/yellow]"
            )
            return

        candidate = find_completion_candidate(text)
        if candidate is None:
            console.print("[yellow]No planned activity found to complete.[/yellow]")
            return

        console.print(format_completion_candidate(candidate))
        console.print()

        if yes:
            confirmed = True
        else:
            answer = typer.prompt(
                "Mark this activity as completed? [y/N]",
                default="",
                show_default=False,
            )
            confirmed = is_affirmative(answer)

        if not confirmed:
            console.print("[yellow]Cancelled. Nothing was updated.[/yellow]")
            return

        updated = complete_activity(candidate.id, confirmed=True)
        if updated is None:
            console.print("[red]Could not update the activity.[/red]")
            raise typer.Exit(code=1)
        console.print(f"[green]Completed:[/green] {updated.title}")

    # ------------------------------------------------------------------
    # Interactive chat mode
    # ------------------------------------------------------------------

    @app.command("chat")
    def chat() -> None:
        """Start an interactive chat session."""
        from life_agent.agent.runtime import AgentRuntime
        from life_agent.agent.safety import is_affirmative
        from life_agent.cli.formatters import (
            format_completion_candidate,
            format_confirmation_proposal,
            format_save_result,
        )
        from life_agent.services.chat_service import (
            GREETING,
            HELP_TEXT,
            UNKNOWN_TEXT,
            ChatIntent,
            classify_intent,
            get_deadlines_response,
            get_query_saved_data_response,
            get_reminders_response,
            get_today_response,
            get_week_response,
        )
        from life_agent.services.completion_service import (
            complete_activity,
            find_completion_candidate,
        )
        from life_agent.services.confirmation_service import (
            build_confirmation_proposal,
            save_confirmed_extraction,
        )
        from life_agent.services.extraction_service import extract_from_text

        console.print(GREETING)
        runtime = AgentRuntime()

        while True:
            try:
                user_input = console.input("\n[bold]You:[/bold] ")
            except (EOFError, KeyboardInterrupt):
                console.print("\nBye!")
                break

            stripped = user_input.strip()
            if not stripped:
                continue

            intent = classify_intent(stripped)

            if intent == ChatIntent.QUIT:
                console.print("Bye!")
                break

            if intent == ChatIntent.HELP:
                console.print(HELP_TEXT)
                continue

            if intent == ChatIntent.TODAY:
                console.print(get_today_response())
                continue

            if intent == ChatIntent.WEEK:
                console.print(get_week_response())
                continue

            if intent == ChatIntent.DEADLINES:
                console.print(get_deadlines_response())
                continue

            if intent == ChatIntent.REMINDERS:
                console.print(get_reminders_response())
                continue

            if intent == ChatIntent.QUERY_SAVED_DATA:
                console.print(get_query_saved_data_response(stripped))
                continue

            if intent == ChatIntent.ADD_ITEMS:
                result = extract_from_text(stripped)
                proposal = build_confirmation_proposal(result)
                console.print(format_confirmation_proposal(proposal))
                console.print()

                if proposal.saveable_count == 0:
                    console.print(
                        "[yellow]Nothing to save. No items were stored.[/yellow]"
                    )
                    continue

                answer = console.input("Save this? [y/N] ")
                if is_affirmative(answer):
                    save_result = save_confirmed_extraction(
                        result, confirmed=True
                    )
                    console.print(format_save_result(save_result))
                else:
                    console.print(
                        "[yellow]Cancelled. Nothing was saved.[/yellow]"
                    )
                continue

            if intent == ChatIntent.COMPLETE:
                candidate = find_completion_candidate(stripped)
                if candidate is None:
                    console.print(
                        "[yellow]No planned activity found to complete.[/yellow]"
                    )
                    continue

                console.print(format_completion_candidate(candidate))
                console.print()
                answer = console.input(
                    "Mark this activity as completed? [y/N] "
                )
                if is_affirmative(answer):
                    updated = complete_activity(
                        candidate.id, confirmed=True
                    )
                    if updated is None:
                        console.print(
                            "[red]Could not update the activity.[/red]"
                        )
                    else:
                        console.print(
                            f"[green]Completed:[/green] {updated.title}"
                        )
                else:
                    console.print(
                        "[yellow]Cancelled. Nothing was updated.[/yellow]"
                    )
                continue

            # UNKNOWN — try conversational LLM fallback via AgentRuntime
            resp = runtime.handle_message(stripped)
            if resp.kind == "display":
                console.print(resp.text)
            else:
                console.print(UNKNOWN_TEXT)

    # ------------------------------------------------------------------
    # LLM-first agent loop (spike — see docs/llm-first-pivot.md)
    # ------------------------------------------------------------------

    @app.command("agent")
    def agent() -> None:
        """Talk to the LLM-driven agent (spike entry point for `chat`)."""
        from rich.markup import escape

        from life_agent.agent.conversation import ConversationAgent
        from life_agent.agent.safety import is_affirmative
        from life_agent.cli.formatters import (
            format_completion_candidate,
            format_confirmation_proposal,
            format_save_result,
        )
        from life_agent.services.completion_service import complete_activity
        from life_agent.services.confirmation_service import save_confirmed_extraction

        quit_words = {"/quit", "/exit", "quit", "exit", "bye", "hejdå", "avsluta"}

        console.print(
            "Hello! Just tell me what is going on — I will figure out the rest.\n"
            "Nothing is saved until you say yes.  Type /quit to leave."
        )
        conversation = ConversationAgent()

        while True:
            try:
                user_input = console.input("\n[bold]You:[/bold] ")
            except (EOFError, KeyboardInterrupt):
                console.print("\nBye!")
                break

            stripped = user_input.strip()
            if not stripped:
                continue
            if stripped.lower() in quit_words:
                console.print("Bye!")
                break

            turn = conversation.send(stripped)
            if turn.reply:
                console.print(f"[cyan]Agent:[/cyan] {escape(turn.reply)}")

            if turn.kind == "display":
                console.print()
                console.print(turn.text)
                continue

            if turn.kind == "reply":
                if turn.proposal is not None:
                    console.print(
                        "[yellow]Nothing complete enough to save yet.[/yellow]"
                    )
                continue

            flow = turn.data.get("flow")

            if flow == "save":
                console.print()
                console.print(format_confirmation_proposal(turn.proposal))
                console.print()
                if is_affirmative(console.input("Save this? [y/N] ")):
                    outcome = format_save_result(
                        save_confirmed_extraction(turn.extraction, confirmed=True)
                    )
                    console.print(f"[bold green]{outcome}[/bold green]")
                else:
                    outcome = "Cancelled. Nothing was saved."
                    console.print(f"[bold yellow]{outcome}[/bold yellow]")
                # The database, not the model, gets the last word on what happened.
                conversation.record_outcome(outcome)
                continue

            if flow == "complete":
                candidate = turn.data["candidate"]
                console.print()
                console.print(format_completion_candidate(candidate))
                console.print()
                if is_affirmative(
                    console.input("Mark this activity as completed? [y/N] ")
                ):
                    updated = complete_activity(candidate.id, confirmed=True)
                    outcome = (
                        f"Completed: {updated.title}"
                        if updated is not None
                        else "Could not update the activity."
                    )
                    console.print(f"[bold green]{outcome}[/bold green]")
                else:
                    outcome = "Cancelled. Nothing was updated."
                    console.print(f"[bold yellow]{outcome}[/bold yellow]")
                conversation.record_outcome(outcome)
