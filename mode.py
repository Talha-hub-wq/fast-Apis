def get_active_sessions_for_user(self, user_email: str) -> List[str]:
        """
        Get all active session IDs for a user.
        
        Args:
            user_email: User's email address
            
        Returns:
            List of active session IDs
        """
        active_sessions = []
        for session_id, session in self.chat_sessions.items():
            if session.user_email == user_email:
                active_sessions.append(session_id)
        return active_sessions