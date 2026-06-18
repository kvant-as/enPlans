def build_html(message_body, email_type):
    if email_type == "code":
        content = f"""
        <div style="padding: 24px 32px;">
            <p style="margin: 0 0 12px 0; font-size: 15px; line-height: 1.5; color: #334155;">Здравствуйте!</p>
            <p style="margin: 0 0 12px 0; font-size: 15px; line-height: 1.5; color: #334155;">Кто-то пытается войти в <strong style="color: #00798f;">EnPlans</strong> используя вашу электронную почту.</p>
            <p style="margin: 0 0 16px 0; font-size: 15px; line-height: 1.5; color: #334155;">Ваш код активации:</p>
            <div style="text-align: center; background: #f1f5f9; border-radius: 12px; padding: 20px; margin: 20px 0;">
                <span style="font-size: 36px; font-weight: 700; letter-spacing: 8px; color: #00798f; font-family: 'Courier New', monospace;">{message_body}</span>
            </div>
            <p style="margin: 20px 0 0 0; font-size: 13px; color: #94a3b8;">Код действителен в течение 10 минут.</p>
        </div>
        """
    elif email_type == "plan":
        status = message_body
        if status == "В редакции":
            color = "#64748b"  # status-sent
        elif status == "Есть ошибки":
            color = "#ef4444"  # status-error
        elif status == "Контроль пройден":
            color = "#8b5cf6"  # status-control
        elif status == "На рассмотрении" or status == "Не просмотрен":
            color = "#3b82f6"  # status-sent
        elif status == "Согласован":
            color = "#10b981"  # status-approved
        else:
            color = "#00798f"  # цвет по умолчанию (EnPlans green)
        
        content = f"""
        <div style="padding: 24px 32px;">
            <p style="margin: 0 0 12px 0; font-size: 15px; line-height: 1.5; color: #334155;">Здравствуйте!</p>
            <p style="margin: 0 0 16px 0; font-size: 15px; line-height: 1.5; color: #334155;">Статус вашего плана энергосбережения изменен на:</p>
            <div style="text-align: center; margin: 24px 0;">
                <span style="display: inline-block; background: {color}10; border-left: 3px solid {color}; padding: 10px 24px; border-radius: 8px; font-size: 18px; font-weight: 600; color: {color};">{status}</span>
            </div>
            <p style="margin: 16px 0 0 0; font-size: 14px; color: #64748b;">Вы можете отслеживать дальнейшие изменения в личном кабинете.</p>
        </div>
        """
    elif email_type == "reset_link":
        content = f"""
        <div style="padding: 24px 32px;">
            <p style="margin: 0 0 12px 0; font-size: 15px; line-height: 1.5; color: #334155;">Здравствуйте!</p>
            <p style="margin: 0 0 12px 0; font-size: 15px; line-height: 1.5; color: #334155;">Вы запросили сброс пароля для вашей учетной записи в <strong style="color: #00798f;">EnPlans</strong>.</p>
            <p style="margin: 0 0 20px 0; font-size: 15px; line-height: 1.5; color: #334155;">Для сброса пароля нажмите на кнопку ниже:</p>
            <div style="text-align: center; margin: 28px 0;">
                <a href="{message_body}" style="display: inline-flex; align-items: center; gap: 8px; background: linear-gradient(135deg, #00798f 0%, #009bb6 100%); color: white; padding: 12px 32px; text-decoration: none; border-radius: 10px; font-size: 15px; font-weight: 500;">Сбросить пароль</a>
            </div>
            <div style="background: #fef2f2; padding: 12px 16px; border-radius: 8px; margin: 20px 0;">
                <p style="margin: 0; font-size: 13px; color: #dc2626;">Ссылка действительна в течение 1 часа.</p>
            </div>
            <p style="margin: 16px 0 0 0; font-size: 13px; color: #94a3b8;">Если вы не запрашивали сброс пароля, проигнорируйте это письмо.</p>
        </div>
        """
    elif email_type == "registration":
        content = f"""
        <div style="padding: 24px 32px;">
            <p style="margin: 0 0 12px 0; font-size: 15px; line-height: 1.5; color: #334155;">Здравствуйте, {message_body}!</p>
            <p style="margin: 0 0 12px 0; font-size: 15px; line-height: 1.5; color: #334155;">Вы успешно зарегистрировались в системе <strong style="color: #00798f;">EnPlans</strong> — платформе для планирования и контроля энергосберегающих мероприятий.</p>
            <p style="margin: 0 0 12px 0; font-size: 15px; line-height: 1.5; color: #334155;">Теперь вы можете:</p>
            <div style="text-align: center; margin: 28px 0 20px 0;">
                <a href="https://EnPlans.energoeffect.gov.by/login" style="display: inline-flex; align-items: center; gap: 8px; background: linear-gradient(135deg, #00798f 0%, #009bb6 100%); color: white; padding: 12px 32px; text-decoration: none; border-radius: 10px; font-size: 15px; font-weight: 500;">Войти в личный кабинет</a>
            </div>
            <p style="margin: 16px 0 0 0; font-size: 13px; color: #94a3b8;">Если вы не регистрировались в системе, проигнорируйте это письмо.</p>
        </div>
        """
    elif email_type == "notification":
        content = f"""
        <div style="padding: 24px 32px;">
            <p style="margin: 0 0 12px 0; font-size: 15px; line-height: 1.5; color: #334155;">Здравствуйте!</p>
            <div style="background: #f1f5f9; border-radius: 12px; padding: 20px; margin: 20px 0;">
                <p style="margin: 0; font-size: 15px; line-height: 1.5; color: #334155;">{message_body}</p>
            </div>
            <p style="margin: 16px 0 0 0; font-size: 13px; color: #94a3b8;">Вы можете просмотреть подробности в <strong style="color: #00798f;">часто задаваемых вопросах</strong>.</p>
        </div>
        """
    else:
        content = f"""
        <div style="padding: 24px 32px;">
            <p style="margin: 0; font-size: 15px; line-height: 1.5; color: #334155;">{message_body}</p>
        </div>
        """

    html_template = f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>EnPlans</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: 'Montserrat', -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
                background-color: #f1f5f9;
                margin: 0;
                padding: 24px;
                line-height: 1.5;
            }}
            
            .email-container {{
                max-width: 560px;
                margin: 0 auto;
                background-color: #ffffff;
                border-radius: 20px;
                overflow: hidden;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05), 0 1px 2px rgba(0, 0, 0, 0.03);
                border: 1px solid #e2e8f0;
            }}
            
            .email-header {{
                background: linear-gradient(135deg, #00798f 0%, #009bb6 100%);
                padding: 28px 32px;
                text-align: center;
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            }}
            
            .email-header h1 {{
                font-size: 22px;
                font-weight: 600;
                color: #ffffff;
                margin: 0;
                letter-spacing: -0.3px;
            }}
            
            .email-header p {{
                font-size: 13px;
                color: rgba(255, 255, 255, 0.8);
                margin: 8px 0 0 0;
            }}
            
            .email-content {{
                padding: 0;
            }}
            
            .email-footer {{
                background-color: #f8fafc;
                padding: 20px 32px;
                text-align: center;
                border-top: 1px solid #e2e8f0;
            }}
            
            .email-footer p {{
                margin: 6px 0;
                font-size: 12px;
                color: #94a3b8;
            }}
            
            .email-footer a {{
                color: #00798f;
                text-decoration: none;
            }}
            
            .email-footer a:hover {{
                text-decoration: underline;
            }}
            
            hr {{
                border: none;
                height: 1px;
                background: linear-gradient(90deg, transparent, #e2e8f0, transparent);
                margin: 20px 0;
            }}
            
            ul {{
                margin: 12px 0 20px 20px;
                padding: 0;
            }}
            
            li {{
                margin: 8px 0;
            }}
        </style>
    </head>
    <body>
        <div class="email-container">
            <div class="email-content">
                {content}
            </div>
            <div class="email-footer">
                <p>© 2026 "Департамент по энергоэффективности" Все права защищены.</p>
                <p>Это автоматическое сообщение, пожалуйста, не отвечайте на него.</p>
            </div>
        </div>
    </body>
    </html>
    """

    return html_template