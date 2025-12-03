"""Constants for Chibi bot."""

# Discord platform limits
DISCORD_MESSAGE_LIMIT = 2000
DISCORD_CHUNK_SIZE = 1990
DISCORD_AUTOCOMPLETE_LIMIT = 25

# Quiz settings
QUIZ_TIMEOUT_MINUTES = 30
QUIZ_QUALITY_SCORE_MIN = 1
QUIZ_QUALITY_SCORE_MAX = 5

# LLM Temperature values
TEMPERATURE_QUIZ_GENERATION = 0.8
TEMPERATURE_EVALUATION = 0.3

# Content truncation limits
MODULE_CONTENT_MAX_LENGTH = 4000
QUIZ_CONTENT_MAX_LENGTH = 3000

# Display limits for status embeds
CONCEPTS_PER_MODULE_LIMIT = 10
CONCEPTS_PER_LEVEL_LIMIT = 8
PROGRESS_BAR_LENGTH = 20

# Mastery level thresholds (used in quiz.py _calculate_mastery_level)
MASTERY_RATIO_MASTERED = 0.85
MASTERY_RATIO_PROFICIENT = 0.6
MASTERY_RATIO_LEARNING = 0.3
MASTERY_QUALITY_MASTERED = 4.0

# Mastery level string constants
MASTERY_NOVICE = "novice"
MASTERY_LEARNING = "learning"
MASTERY_PROFICIENT = "proficient"
MASTERY_MASTERED = "mastered"

# Mastery emoji mapping
MASTERY_EMOJI = {
    MASTERY_MASTERED: "🏆",
    MASTERY_PROFICIENT: "⭐",
    MASTERY_LEARNING: "📖",
    MASTERY_NOVICE: "🌱",
}

# Error messages
ERROR_GENERIC = "Oops! Something went wrong. Please try again! 🔧"
ERROR_QUIZ = "Oops! Something went wrong while generating your quiz. Please try again! 🔧"
ERROR_STATUS = "Oops! Something went wrong while fetching your status. Please try again! 🔧"
ERROR_MODULE_NOT_FOUND = "Could not find the specified module. Please try again! 📚"
ERROR_NO_CONCEPTS = "No concepts found for this module. Please try a different module! 📖"
ERROR_ADMIN_ONLY = "This command is only available to administrators."
ERROR_ADMIN_CHANNEL_ONLY = "This command can only be used in the admin channel."
ERROR_ADMIN_CHANNEL_NOT_CONFIGURED = "Admin channel is not configured. Please set ADMIN_CHANNEL_ID in .env file."
ERROR_SHOW_GRADE = "Failed to generate grade report. Please try again."
ERROR_STUDENT_NOT_FOUND = "Could not find a student with that identifier. Please check the Discord ID or username."
ERROR_STUDENT_STATUS = "Failed to fetch student status. Please try again."

# Admin command settings
CSV_FILENAME_PREFIX = "student_grades"
EMBED_FIELD_CHUNK_SIZE = 15  # Max items per embed field for student lists
DESCRIPTION_TRUNCATE_LENGTH = 100  # Max length for truncated descriptions

# Attendance error messages
ERROR_ATTENDANCE_SESSION_ACTIVE = "An attendance session is already active. Please close it first."
ERROR_NO_ACTIVE_SESSION = "No active attendance session. Please wait for the instructor to start attendance."
ERROR_INVALID_CODE = "Invalid or expired code. Please use the current code shown on screen."
ERROR_ATTENDANCE_CHANNEL_NOT_CONFIGURED = "Attendance channel is not configured. Please set ATTENDANCE_CHANNEL_ID in .env file."
ERROR_ATTENDANCE_CHANNEL_ONLY = "This command can only be used in the attendance channel."
ERROR_ATTENDANCE_EXPORT = "Failed to export attendance records."
ERROR_STUDENT_REGISTRATION_FAILED = "Failed to register student information."

# Attendance settings
ATTENDANCE_CSV_PREFIX = "attendance"
