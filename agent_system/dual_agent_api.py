#!/usr/bin/env python3
"""
Dual Agent Integration API
Phase 3: 职能分工与记忆增强体系 - HTTP API 端点

提供统一的HTTP接口供主代理和子代理调用
"""

import json
import sys
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any

# 添加模块路径
sys.path.insert(0, '/var/www/ai-god-of-stocks/agent_system')

from shared_memory_system import get_shared_memory, AgentState
from task_coordinator import get_task_coordinator, TaskPriority, TaskStatus
from memory_bridge import get_memory_bridge

# 共享记忆系统
sms = get_shared_memory()
tc = get_task_coordinator()
mb = get_memory_bridge()


class DualAgentHandler(BaseHTTPRequestHandler):
    """双代理集成API处理器"""
    
    def log_message(self, format, *args):
        """自定义日志格式"""
        print(f"[DualAgentAPI] {self.client_address[0]} - {format % args}")
    
    def _send_json(self, data: Dict[str, Any], status: int = 200):
        """发送JSON响应"""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, default=lambda x: x.value if hasattr(x, 'value') else x).encode())
    
    def _send_error(self, message: str, status: int = 400):
        """发送错误响应"""
        self._send_json({"error": message}, status)
    
    def _get_body(self) -> Dict[str, Any]:
        """获取请求体"""
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length > 0:
            body = self.rfile.read(content_length).decode()
            return json.loads(body)
        return {}
    
    def do_GET(self):
        """处理GET请求"""
        path = self.path
        
        # 健康检查
        if path == '/health':
            self._send_json({
                "status": "ok",
                "services": {
                    "shared_memory": True,
                    "task_coordinator": True,
                    "memory_bridge": True
                }
            })
            return
        
        # 获取代理状态
        if path.startswith('/agents/'):
            agent_id = path.split('/')[-1]
            state = sms.get_agent_state(agent_id)
            if state:
                self._send_json({
                    "agent_id": state.agent_id,
                    "status": state.status,
                    "last_heartbeat": state.last_heartbeat,
                    "current_task": state.current_task,
                    "task_progress": state.task_progress
                })
            else:
                self._send_error("Agent not found", 404)
            return
        
        # 获取所有代理状态
        if path == '/agents':
            states = sms.get_all_agent_states()
            self._send_json({
                "agents": [
                    {
                        "agent_id": s.agent_id,
                        "status": s.status,
                        "last_heartbeat": s.last_heartbeat
                    }
                    for s in states.values()
                ]
            })
            return
        
        # 获取任务状态
        if path.startswith('/tasks/'):
            task_id = path.split('/')[-1]
            task = tc.get_task(task_id)
            if task:
                self._send_json({
                    "task_id": task.task_id,
                    "task_type": task.task_type,
                    "status": task.status.value,
                    "priority": task.priority.value,
                    "assigned_agent": task.assigned_agent,
                    "result": task.result,
                    "error": task.error
                })
            else:
                self._send_error("Task not found", 404)
            return
        
        # 获取待处理任务
        if path == '/tasks/pending':
            tasks = tc.get_pending_tasks()
            self._send_json({
                "tasks": [
                    {
                        "task_id": t.task_id,
                        "task_type": t.task_type,
                        "priority": t.priority.value
                    }
                    for t in tasks
                ]
            })
            return
        
        # 获取缓存统计
        if path == '/cache/stats':
            stats = sms.get_cache_stats()
            self._send_json(stats)
            return
        
        # 获取记忆统计
        if path == '/memory/stats':
            stats = mb.get_memory_stats()
            self._send_json(stats)
            return
        
        self._send_error("Not found", 404)
    
    def do_POST(self):
        """处理POST请求"""
        path = self.path
        body = self._get_body()
        
        # 更新代理状态
        if path == '/agents/status':
            agent_id = body.get('agent_id')
            status = body.get('status')
            current_task = body.get('current_task')
            task_progress = body.get('task_progress', 0.0)
            
            if not agent_id or not status:
                self._send_error("Missing agent_id or status")
                return
            
            state = AgentState(
                agent_id=agent_id,
                status=status,
                last_heartbeat=__import__('time').time(),
                current_task=current_task,
                task_progress=task_progress
            )
            
            if sms.update_agent_state(state):
                self._send_json({"success": True, "agent_id": agent_id})
            else:
                self._send_error("Failed to update state", 500)
            return
        
        # 创建任务
        if path == '/tasks':
            task_type = body.get('task_type')
            payload = body.get('payload', {})
            priority_str = body.get('priority', 'NORMAL')
            
            if not task_type:
                self._send_error("Missing task_type")
                return
            
            try:
                priority = TaskPriority[priority_str.upper()]
            except KeyError:
                priority = TaskPriority.NORMAL
            
            task_id = tc.create_task(task_type, payload, priority)
            self._send_json({"success": True, "task_id": task_id})
            return
        
        # 完成任务
        if path.startswith('/tasks/') and path.endswith('/complete'):
            task_id = path.split('/')[-2]
            result = body.get('result')
            error = body.get('error')
            
            if tc.complete_task(task_id, result, error):
                self._send_json({"success": True, "task_id": task_id})
            else:
                self._send_error("Failed to complete task", 500)
            return
        
        # 添加记忆
        if path == '/memory':
            source_agent = body.get('source_agent')
            target_agents = body.get('target_agents', [])
            memory_type = body.get('memory_type', 'observation')
            content = body.get('content')
            context = body.get('context', {})
            importance = body.get('importance', 5)
            ttl_hours = body.get('ttl_hours')
            
            if not source_agent or not content:
                self._send_error("Missing source_agent or content")
                return
            
            mem_id = mb.add_memory(
                source_agent=source_agent,
                target_agents=target_agents,
                memory_type=memory_type,
                content=content,
                context=context,
                importance=importance,
                ttl_hours=ttl_hours
            )
            
            self._send_json({"success": True, "memory_id": mem_id})
            return
        
        # 获取缓存
        if path == '/cache/get':
            query_type = body.get('query_type')
            params = body.get('params', {})
            
            if not query_type:
                self._send_error("Missing query_type")
                return
            
            cached = sms.get_cached_response(query_type, params)
            if cached:
                self._send_json({"hit": True, "data": cached})
            else:
                self._send_json({"hit": False})
            return
        
        # 设置缓存
        if path == '/cache/set':
            query_type = body.get('query_type')
            params = body.get('params', {})
            data = body.get('data')
            ttl = body.get('ttl')
            
            if not query_type or data is None:
                self._send_error("Missing query_type or data")
                return
            
            sms.cache_response(query_type, params, data, ttl)
            self._send_json({"success": True})
            return
        
        # 自动分配任务
        if path == '/tasks/auto-assign':
            assigned = tc.auto_assign_tasks()
            self._send_json({"success": True, "assigned": assigned})
            return
        
        self._send_error("Not found", 404)
    
    def do_OPTIONS(self):
        """处理OPTIONS请求 (CORS)"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()


def run_server(port: int = 18087):
    """运行API服务器"""
    server = HTTPServer(('127.0.0.1', port), DualAgentHandler)
    print(f"[DualAgentAPI] Server running on http://127.0.0.1:{port}")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[DualAgentAPI] Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Dual Agent Integration API')
    parser.add_argument('--port', type=int, default=18087, help='Server port')
    args = parser.parse_args()
    
    run_server(args.port)
