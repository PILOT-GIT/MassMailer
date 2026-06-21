from aiogram.fsm.state import State, StatesGroup

class ApprovalFlowStates(StatesGroup):
    waiting_for_approval = State()

class GmailAuthStates(StatesGroup):
    email_input = State()
    password_input = State()

class TargetListStates(StatesGroup):
    entering_list_name = State()
    uploading_csv = State()

class CampaignCreationStates(StatesGroup):
    selecting_target_list = State()
    selecting_sender = State()
    entering_subject = State()
    entering_body = State()
    entering_address = State()
    selecting_schedule = State()
    entering_custom_time = State()
    confirming_campaign = State()
