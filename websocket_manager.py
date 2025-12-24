from fastapi import WebSocket
from typing import Dict, List
import json
from datetime import datetime

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, Dict] = {}
    
    async def connect(self, websocket: WebSocket, user_id: int, user_role: str = None):
        """Connect a new WebSocket"""
        await websocket.accept()
        self.active_connections[user_id] = {
            'ws': websocket,
            'role': user_role
        }
        print(f"User {user_id} (role: {user_role}) connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket, user_id: int):
        """Disconnect a WebSocket"""
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            print(f"User {user_id} disconnected")
    
    async def broadcast_alert(self, alert_data: dict, target_roles: List[str] = None):
        """
        Broadcast alert to users based on target_roles.
        If target_roles is None or contains "all", broadcast to everyone.
        Otherwise, only send to users whose role matches target_roles.
        """
        if not target_roles:
            target_roles = ["all"]
        
        normalized_roles = []
        for role in target_roles:
            role_lower = role.lower()
            if role_lower == 'students':
                normalized_roles.append('student')
            else:
                normalized_roles.append(role_lower)
        
        broadcast_to_all = "all" in normalized_roles
        
        disconnected_users = []
        for user_id, connection_info in self.active_connections.items():
            websocket = connection_info['ws']
            user_role = connection_info.get('role', '')
            
            should_receive = broadcast_to_all or user_role in normalized_roles
            
            if should_receive:
                try:
                    await websocket.send_json({
                        "type": "new_alert",
                        "alert": alert_data,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                except Exception as e:
                    print(f"Error sending to user {user_id}: {e}")
                    disconnected_users.append(user_id)
        
        for user_id in disconnected_users:
            if user_id in self.active_connections:
                del self.active_connections[user_id]
    
    async def broadcast_reaction(self, reaction_data: dict):
        """Broadcast reaction update to all connected users"""
        disconnected_users = []
        for user_id, connection_info in self.active_connections.items():
            websocket = connection_info['ws']
            try:
                await websocket.send_json({
                    "type": "reaction_update",
                    "reaction": reaction_data,
                    "timestamp": datetime.utcnow().isoformat()
                })
            except Exception as e:
                print(f"Error sending reaction to user {user_id}: {e}")
                disconnected_users.append(user_id)
        
        for user_id in disconnected_users:
            if user_id in self.active_connections:
                del self.active_connections[user_id]
    
    async def broadcast_alert_deletion(self, alert_id: int):
        """Broadcast alert deletion to all connected users"""
        disconnected_users = []
        for user_id, connection_info in self.active_connections.items():
            websocket = connection_info['ws']
            try:
                await websocket.send_json({
                    "type": "alert_deleted",
                    "alert_id": alert_id,
                    "timestamp": datetime.utcnow().isoformat()
                })
            except Exception as e:
                print(f"Error sending deletion to user {user_id}: {e}")
                disconnected_users.append(user_id)
        
        for user_id in disconnected_users:
            if user_id in self.active_connections:
                del self.active_connections[user_id]
    
    async def broadcast_acknowledgment(self, ack_data: dict):
        """Broadcast acknowledgment update to all connected users"""
        disconnected_users = []
        for user_id, connection_info in self.active_connections.items():
            websocket = connection_info['ws']
            try:
                await websocket.send_json({
                    "type": "acknowledgment_update",
                    "acknowledgment": ack_data,
                    "timestamp": datetime.utcnow().isoformat()
                })
            except Exception as e:
                print(f"Error sending acknowledgment to user {user_id}: {e}")
                disconnected_users.append(user_id)
        
        for user_id in disconnected_users:
            if user_id in self.active_connections:
                del self.active_connections[user_id]
    
    def get_active_users_count(self) -> int:
        """Get count of active connections"""
        return len(self.active_connections)

ws_manager = ConnectionManager()
