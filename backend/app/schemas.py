from datetime import date, datetime, time
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Role = Literal['admin', 'hr', 'manager', 'employee']

class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

class Login(Input):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=128)

class PasswordChange(Input):
    current_password: str = Field(max_length=128)
    new_password: str = Field(min_length=10, max_length=128)

class UserInput(Input):
    code: str = Field(min_length=2, max_length=30, pattern=r'^[A-Za-z0-9_-]+$')
    name: str = Field(min_length=2, max_length=100)
    username: str = Field(min_length=3, max_length=80, pattern=r'^[a-zA-Z0-9_.@-]+$')
    password: str | None = Field(default=None, min_length=10, max_length=128)
    role: Role = 'employee'
    department_id: str | None = None
    title: str = Field(default='', max_length=100)
    phone: str = Field(default='', max_length=30)
    joined_date: date
    active: bool = True

class DepartmentInput(Input):
    name: str = Field(min_length=2, max_length=100)
    description: str = Field(default='', max_length=300)
    manager_id: str | None = None

class ShiftInput(Input):
    name: str = Field(min_length=2, max_length=80)
    start: time
    end: time
    break_start: time | None = None
    break_end: time | None = None
    grace_minutes: int = Field(default=5, ge=0, le=60)
    color: str = Field(default='#2563eb', pattern=r'^#[0-9a-fA-F]{6}$')
    active: bool = True

    @model_validator(mode='after')
    def validate_break(self):
        def minute(t): return t.hour * 60 + t.minute
        start, end = minute(self.start), minute(self.end)
        duration = (end - start) % 1440
        if not 60 <= duration <= 960:
            raise ValueError('Ca làm phải dài từ 1 đến 16 giờ')
        if (self.break_start is None) != (self.break_end is None):
            raise ValueError('Nhập đủ giờ bắt đầu và kết thúc nghỉ giữa ca')
        if self.break_start:
            bs, be = (minute(self.break_start)-start)%1440, (minute(self.break_end)-start)%1440
            if not 0 <= bs < be <= duration:
                raise ValueError('Khoảng nghỉ phải nằm trong ca làm')
        return self

class AssignmentInput(Input):
    user_ids: list[str] = Field(min_length=1, max_length=100)
    shift_id: str
    start_date: date
    end_date: date
    weekdays: list[int] = Field(default=[0, 1, 2, 3, 4], min_length=1, max_length=7)

    @model_validator(mode='after')
    def range_valid(self):
        if not 0 <= (self.end_date - self.start_date).days <= 62:
            raise ValueError('Phân ca tối đa 63 ngày, ngày kết thúc không trước ngày bắt đầu')
        if any(x not in range(7) for x in self.weekdays):
            raise ValueError('Thứ trong tuần phải từ 0 đến 6')
        return self

class HolidayInput(Input):
    date: date
    name: str = Field(min_length=2, max_length=100)

class PunchInput(Input):
    assignment_id: str
    action: Literal['in', 'out']

class RequestInput(Input):
    type: Literal['leave', 'correction', 'overtime', 'remote', 'business', 'late_early']
    start_date: date
    end_date: date
    reason: str = Field(min_length=5, max_length=1000)
    paid: bool = True
    leave_hours: float = Field(default=8, gt=0, le=16)
    check_in: datetime | None = None
    check_out: datetime | None = None

    @model_validator(mode='after')
    def valid(self):
        if not 0 <= (self.end_date-self.start_date).days <= 31:
            raise ValueError('Khoảng ngày không hợp lệ, tối đa 32 ngày')
        if self.type in ['correction', 'overtime']:
            if self.start_date != self.end_date or not self.check_in or not self.check_out:
                raise ValueError('Sửa công / tăng ca cần một ngày và đủ giờ bắt đầu, kết thúc')
            if not self.check_in.tzinfo or not self.check_out.tzinfo:
                raise ValueError('Thời gian phải có múi giờ')
            if not 0 < (self.check_out-self.check_in).total_seconds() <= 86400:
                raise ValueError('Khoảng giờ phải lớn hơn 0 và không quá 24 giờ')
        return self

class DecisionInput(Input):
    status: Literal['approved', 'rejected']
    note: str = Field(min_length=3, max_length=500)

class ReasonInput(Input):
    reason: str = Field(min_length=5, max_length=500)

class FaceFrame(Input):
    image: str = Field(min_length=30, max_length=1_600_000)

class FaceEnroll(FaceFrame):
    consent: bool

class FacePunch(FaceFrame):
    assignment_id: str
    action: Literal['in', 'out']
    attempt_id: str = Field(min_length=16, max_length=80, pattern=r'^[a-zA-Z0-9-]+$')
