import smtplib
import os
import time
import logging
import uuid
import socket
from queue import PriorityQueue, Empty
from threading import Thread, Lock
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
from .email_html import build_html

SMTP_HOST = os.getenv("SMTP_HOST")

EMAILS_PER_MINUTE = 6
DAILY_LIMIT = 10000

PRIORITY = {
    "activation_code": 3,
    "new_pass": 3,
    "to_admin": 1,
    "to_recipient": 1,
    "default": 0
}

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("email-service")


def safe_email_log(email, show_chars=4):
    if not email or '@' not in email:
        return email
    
    local, domain = email.split('@', 1)

    if len(local) > show_chars:
        masked_local = local[:show_chars] + '*' * (len(local) - show_chars)
    else:
        masked_local = local + '*' * (show_chars - len(local))
    return f"{masked_local}@{domain}"


def safe_subject_log(subject, max_len=30):
    if not subject:
        return "<пусто>"
    if len(subject) > max_len:
        return subject[:max_len] + "..."
    return subject

class Worker(Thread):
    def __init__(self, email, password, acc_id, queue):
        super().__init__(daemon=True)
        self.email = email
        self.password = password
        self.acc_id = acc_id
        self.queue = queue

        self.sent_today = 0
        self.last_sent = 0
        self.lock = Lock()
        
        self.stats = {
            "success": 0,
            "failed": 0,
            "retries": 0,
            "connection_errors": 0,
            "auth_errors": 0,
            "timeout_errors": 0,
            "other_errors": 0
        }
        self.stats_lock = Lock()

        self.start()

    def can_send(self):
        if self.sent_today >= DAILY_LIMIT:
            return False
        if time.time() - self.last_sent < 60 / EMAILS_PER_MINUTE:
            return False
        return True

    def log_error(self, error_type, port, task_info, error_details, exc_info=False):
        with self.stats_lock:
            self.stats[error_type] = self.stats.get(error_type, 0) + 1
        
        masked_to = safe_email_log(task_info.get("to", "unknown"))
        masked_subject = safe_subject_log(task_info.get("subject", ""))
        
        log.error(
            f"[ACC {self.acc_id}] {error_type.upper()} | "
            f"порт:{port} | "
            f"получатель:{masked_to} | "
            f"тема:{masked_subject} | "
            f"попытка:{task_info.get('attempt', 0)} | "
            f"тип:{task_info.get('type', 'unknown')} | "
            f"ошибка:{error_details}",
            exc_info=exc_info
        )

    def send_email(self, to_email, subject, html, task_info):
        ports_to_try = [465, 587]
        last_error = None

        masked_to = safe_email_log(to_email)
        masked_from = safe_email_log(self.email)

        for port in ports_to_try:
            try:
                log.info(f"[ACC {self.acc_id}] Попытка отправки -> {masked_to} через порт {port} (попытка {task_info.get('attempt', 0)+1})")

                server = None
                if port == 465:
                    server = smtplib.SMTP_SSL(SMTP_HOST, port, timeout=20)
                else:
                    server = smtplib.SMTP(SMTP_HOST, port, timeout=20)
                    server.starttls()

                server.ehlo()
                server.set_debuglevel(0)

                log.info(f"[ACC {self.acc_id}] Авторизация SMTP ({masked_from})")
                server.login(self.email, self.password)

                msg = MIMEMultipart()
                msg["From"] = self.email
                msg["To"] = to_email
                msg["Subject"] = subject
                msg["Date"] = formatdate(localtime=True)
                msg.attach(MIMEText(html, "html"))

                server.sendmail(self.email, to_email, msg.as_string())
                server.quit()

                with self.lock:
                    self.sent_today += 1
                    self.last_sent = time.time()
                    self.stats["success"] += 1

                log.info(f"[ACC {self.acc_id}] УСПЕХ -> {masked_to} (порт {port})")
                return True

            except smtplib.SMTPAuthenticationError as e:
                error_msg = f"Ошибка аутентификации: {str(e)[:100]}"
                self.log_error("auth_errors", port, task_info, error_msg, exc_info=True)
                last_error = e
                break

            except smtplib.SMTPServerDisconnected as e:
                error_msg = f"Сервер разорвал соединение: {str(e)[:100]}"
                self.log_error("connection_errors", port, task_info, error_msg, exc_info=True)
                last_error = e

            except socket.timeout as e:
                error_msg = f"Таймаут соединения: {str(e)[:100]}"
                self.log_error("timeout_errors", port, task_info, error_msg)
                last_error = e

            except socket.error as e:
                error_msg = f"Ошибка сокета: {str(e)[:100]}"
                self.log_error("connection_errors", port, task_info, error_msg)
                last_error = e

            except smtplib.SMTPException as e:
                error_code = str(e).split()[0] if str(e) else "unknown"
                if error_code.startswith('4'):
                    error_msg = f"Временная ошибка SMTP (код {error_code}): {str(e)[:100]}"
                    self.log_error("connection_errors", port, task_info, error_msg)
                else:
                    error_msg = f"Постоянная ошибка SMTP (код {error_code}): {str(e)[:100]}"
                    self.log_error("other_errors", port, task_info, error_msg)
                last_error = e

            except Exception as e:
                error_msg = f"Неизвестная ошибка: {type(e).__name__}: {str(e)[:100]}"
                self.log_error("other_errors", port, task_info, error_msg, exc_info=True)
                last_error = e

            finally:
                if server:
                    try:
                        server.quit()
                    except:
                        pass

        with self.stats_lock:
            self.stats["failed"] += 1
        return False

    def run(self):
        consecutive_errors = 0
        last_stats_report = time.time()

        while True:
            try:
                if time.time() - last_stats_report > 3600:
                    with self.stats_lock:
                        log.info(f"[ACC {self.acc_id}] Статистика: успех={self.stats['success']}, "
                               f"ошибок={self.stats['failed']}, соединение={self.stats['connection_errors']}, "
                               f"авторизация={self.stats['auth_errors']}")
                    last_stats_report = time.time()

                pr, ts, task = self.queue.get(timeout=1)
                consecutive_errors = 0

            except Empty:
                continue

            if not self.can_send():
                if consecutive_errors > 0:
                    time.sleep(5)
                else:
                    time.sleep(2)
                self.queue.put((pr, ts, task))
                continue

            ok = self.send_email(
                task["to"],
                task["subject"],
                task["html"],
                task
            )

            if not ok:
                consecutive_errors += 1
                
                if task["attempt"] < 3:
                    task["attempt"] += 1
                    wait_time = min(30, 5 * task["attempt"])
                    
                    log.warning(
                        f"[ACC {self.acc_id}] Повтор {task['attempt']}/3 -> "
                        f"{safe_email_log(task['to'])} через {wait_time}с"
                    )
                    
                    with self.stats_lock:
                        self.stats["retries"] += 1
                    
                    time.sleep(wait_time)
                    self.queue.put((pr, time.time(), task))
                else:
                    log.error(
                        f"[ACC {self.acc_id}] ПРОВАЛ -> {safe_email_log(task['to'])} после 3 попыток"
                    )
            else:
                consecutive_errors = 0

            self.queue.task_done()

class EmailQueue:
    def __init__(self):
        self.queue = PriorityQueue()
        self.workers = self._load_accounts()
        self.start_time = time.time()

    def _load_accounts(self):
        workers = []
        i = 1
        while True:
            email = os.getenv(f"ACC_{i}_EMAIL")
            password = os.getenv(f"ACC_{i}_PASS")
            if not email or not password:
                break

            workers.append(
                Worker(
                    email=email,
                    password=password,
                    acc_id=i,
                    queue=self.queue
                )
            )
            i += 1

        if not workers:
            raise RuntimeError("No email accs")

        log.info(f"[QUEUE] Загружено {len(workers)} аккаунтов")
        return workers

    def add(self, to_email, subject, html, email_type="default"):
        pr = -PRIORITY.get(email_type, 0)
        task_id = str(uuid.uuid4())[:8]

        task = {
            "id": task_id,
            "to": to_email,
            "subject": subject,
            "html": html,
            "attempt": 0,
            "type": email_type,
            "created_at": time.time()
        }

        self.queue.put((pr, time.time(), task))

        masked_to = safe_email_log(to_email)
        masked_subject = safe_subject_log(subject)
        log.info(f"[QUEUE] #{task_id} добавлен | "
                f"получатель:{masked_to} | "
                f"тема:{masked_subject} | "
                f"тип:{email_type} | "
                f"приоритет:{PRIORITY.get(email_type, 0)}")

    def get_stats(self):
        total_stats = {
            "success": 0,
            "failed": 0,
            "retries": 0,
            "connection_errors": 0,
            "auth_errors": 0,
            "timeout_errors": 0,
            "other_errors": 0,
            "queue_size": self.queue.qsize(),
            "uptime": time.time() - self.start_time
        }
        
        for worker in self.workers:
            with worker.stats_lock:
                for key in total_stats:
                    if key in worker.stats:
                        total_stats[key] += worker.stats[key]
        
        return total_stats

_email_queue = None

def get_email_queue():
    global _email_queue
    if _email_queue is None:
        _email_queue = EmailQueue()
    return _email_queue

def send_email(message, recipient_email, email_type="default"):
    subject_map = {
        "code": "Код подтверждения enPlans",
        "plan": "Изменение статуса плана enPlans",
        "reset_link": "Сброс пароля enPlans",
        "registration": "Добро пожаловать в enPlans",
        "notification": "Уведомление от enPlans",
    }

    html = build_html(message, email_type)
    subject = subject_map.get(email_type)

    queue = get_email_queue()
    queue.add(
        to_email=recipient_email,
        subject=subject,
        html=html,
        email_type=email_type
    )

    masked_to = safe_email_log(recipient_email)
    log.info(f"[SEND] В очередь -> {masked_to} ({email_type})")

def get_email_stats():
    queue = get_email_queue()
    return queue.get_stats()