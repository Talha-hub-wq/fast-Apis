def continue_chat_session(
        self, 
        session_id: str, 
        user_message: str, 
        resume_text: str, 
        db: Session,
        user
    ) -> Dict:
        """
        Continue an existing chat session and store conversation in DB.
       
        """

        from app.services.mentor_service import MentorService

        if session_id not in self.chat_sessions:
            return {
                "success": False,
                "message": "No active chat session found. Please start a session first."
            }

        session = self.chat_sessions[session_id]

        # Generate timestamp
        timestamp = datetime.now().strftime("%H:%M")

        # Add user message to in-memory history
        session.conversation_history.append({
            "role": "user",
            "content": user_message,
            "timestamp": datetime.now().isoformat()
        })

        # --- AI Processing (same as before) ---
        recent_messages = session.conversation_history[-6:]
        older_messages = session.conversation_history[:-6]

        history_summary = ""
        if older_messages:
            history_summary = self.ai_service.summarize_conversation_history(older_messages)

        system_prompt = self.create_mentor_system_prompt(
            session.original_category,
            resume_text,
            recent_messages,
            db,
            summary_text=history_summary
        )

        messages = [{"role": "system", "content": system_prompt}]
        for msg in recent_messages:
            messages.append({"role": msg["role"], "content": msg["content"]})

        ai_result = self.ai_service.call_openai_api(
            messages=messages,
            temperature=0.7,
            max_tokens=800
        )

        if not ai_result["success"]:
            return {
                "success": False,
                "message": f"AI service error: {ai_result['error']}"
            }

        ai_response = ai_result["content"]

        # Add assistant message to memory
        session.conversation_history.append({
            "role": "assistant",
            "content": ai_response,
            "timestamp": datetime.now().isoformat()
        })

        # --- Create conversation pair in required format ---
        conversation_pair = [
            {timestamp: {"user": user_message}},
            {timestamp: {"assistant": ai_response}}
        ]

        # # user_auth = db.query(UserAuth).filter(UserAuth.email == session.user_email).first()
        # # --- Save / Update DB ---
        # #email = session.user_email
        # chat_db = db.query(ChatSessionDB).filter(ChatSessionDB.user_email == session.user_email).first()

        # # read chat history from db if exists against email

        # chat_history = chat_db.conversation_history
        # # append new conversation pair
        # if chat_history:
        #     chat_history.append(conversation_pair)
        #     chat_db.conversation_history = chat_history

        # # insert in db
        # if not chat_db:
        #     chat_db = ChatSessionDB(
        #         user_id=user.user_id,          # 👈 yahan se lo
        #         user_email=user_auth.email,    # 👈 yahan se lo
        #         session_id=session_id,
        #         conversation_history=[conversation_pair]
        #     )
        #     db.add(chat_db)
        # else:
        #     history = chat_db.conversation_history or []
        #     history.append(conversation_pair)
        #     chat_db.conversation_history = history

        # db.commit()
        # db.refresh(chat_db)

        # --- Save / Update DB ---
        chat_db = db.query(ChatSessionDB).filter(
            ChatSessionDB.user_email == session.user_email
        ).first()

        if chat_db:
            # Agar record already hai
            chat_history = chat_db.conversation_history or []
            chat_history.append(conversation_pair)
            print("Updated chat history:", chat_history)
            chat_db.conversation_history = chat_history
        else:
            # Agar record nahi mila to naya banado
            chat_db = ChatSessionDB(
                user_id=user.user_id,
                user_email=user.email,   # 👈 fix here
                session_id=session_id,
                conversation_history=[conversation_pair]
            )
            db.add(chat_db)

        db.commit()
        db.refresh(chat_db)





        # --- Completion Check (same as before) ---
        completion_check = self.ai_service.check_conversation_completion(
            ai_response, session.conversation_history
        )

        response_data = {
            "message": ai_response,
            "conversation_complete": completion_check.get("complete", False),
            "selected_category": completion_check.get("selected_category"),
            "confidence_score": completion_check.get("confidence", 0)
        }

        if completion_check.get("complete") and completion_check.get("selected_category"):
            session.selected_category = completion_check["selected_category"]

            try:
                mentor_service = MentorService()
                user_info = mentor_service.user_service.get_user_by_email(
                    session.user_email, db
                )

                if user_info and user_info.gaps:
                    gap_analysis = user_info.gaps
                    result = mentor_service.process_resume_complete_flow(
                        gap_analysis,
                        db,
                        session.user_email,
                        session.selected_category
                    )

                    response_data.update({
                        "processing_result": result,
                        "roadmap_generated": True,
                        "final_category": session.selected_category
                    })
                else:
                    response_data["processing_error"] = "User profile or gap analysis not found"

                del self.chat_sessions[session_id]

            except Exception as e:
                response_data["processing_error"] = f"Error generating roadmap: {str(e)}"

        self.chat_sessions[session_id] = session

        return {
            "success": True,
            "response": response_data,
            "session_id": session_id,
            "conversation_length": len(session.conversation_history)
        }

    
    def create_mentor_system_prompt(
        self, 
        original_category: str, 
        resume_text: str, 
        conversation_history: List[Dict], 
        db: Session, 
        summary_text: str = ""
    ) -> str:
        """
        Create a comprehensive system prompt for the mentor agent.
        
        Args:
            original_category: Originally classified category
            resume_text: User's resume text
            conversation_history: Recent conversation messages
            db: Database session
            summary_text: Summary of older conversation
            
        Returns:
            Formatted system prompt for the AI mentor
        """
        from app.services.mentor_service import MentorService
        
        mentor_service = MentorService()
        all_categories = mentor_service.get_all_categories_from_db(db)
        categories_list = ", ".join(all_categories)
        
        conversation_context = ""
        if len(conversation_history) > 0:
            recent_messages = conversation_history[-6:]
            conversation_context = "\n".join([
                f"{msg['role'].upper()}: {msg['content']}" for msg in recent_messages
            ])
        
        summary_block = f"Previous conversation summary: {summary_text}" if summary_text else ""

        prompt = MENTOR_SYSTEM_PROMPT.format(
            original_category=original_category,
            categories_list=categories_list,
            resume_text=resume_text[:1500],  # Limit resume text length
            summary_block=summary_block,
            conversation_context=conversation_context
        )
        
        return prompt
    
    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """
        Get chat session by ID.
        
        Args:
            session_id: Session identifier
            
        Returns:
            ChatSession object or None if not found
        """
        return self.chat_sessions.get(session_id)
    
    def end_session(self, session_id: str) -> bool:
        """
        End and clean up a chat session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if session was found and deleted, False otherwise
        """
        if session_id in self.chat_sessions:
            del self.chat_sessions[session_id]
            return True
        return False
    
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
    
    def cleanup_expired_sessions(self, max_age_hours: int = 24) -> int:
        """
        Clean up expired chat sessions.
        
        Args:
            max_age_hours: Maximum age of sessions to keep (in hours)
            
        Returns:
            Number of sessions cleaned up
        """
        current_time = datetime.now()
        expired_sessions = []
        
        for session_id, session in self.chat_sessions.items():
            if session.conversation_history:
                try:
                    last_message_time = datetime.fromisoformat(
                        session.conversation_history[-1]["timestamp"]
                    )
                    age_hours = (current_time - last_message_time).total_seconds() / 3600
                    
                    if age_hours > max_age_hours:
                        expired_sessions.append(session_id)
                except Exception as e:
                    print(f"Error checking session age for {session_id}: {e}")
                    expired_sessions.append(session_id)  # Remove problematic sessions
        
        # Remove expired sessions
        for session_id in expired_sessions:
            del self.chat_sessions[session_id]
        
        return len(expired_sessions)
