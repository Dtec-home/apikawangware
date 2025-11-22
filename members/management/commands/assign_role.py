"""
Management command to assign roles to users
Usage: python manage.py assign_role <phone_number> <role>
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from members.models import Member
from members.roles import UserRole, RoleType


class Command(BaseCommand):
    help = 'Assign a role to a user by phone number'

    def add_arguments(self, parser):
        parser.add_argument('phone_number', type=str, help='Phone number of the member')
        parser.add_argument('role', type=str, help='Role to assign (admin, treasurer, pastor, member)')

    def handle(self, *args, **options):
        phone_number = options['phone_number']
        role = options['role'].lower()

        # Validate role
        valid_roles = [r.value for r in RoleType]
        if role not in valid_roles:
            self.stdout.write(self.style.ERROR(f'Invalid role. Must be one of: {", ".join(valid_roles)}'))
            return

        try:
            # Find member by phone number
            member = Member.objects.get(phone_number=phone_number, is_deleted=False)

            # Get or create user for this member
            user, created = User.objects.get_or_create(
                username=phone_number,
                defaults={
                    'first_name': member.first_name,
                    'last_name': member.last_name,
                    'email': member.email or '',
                }
            )

            if created:
                self.stdout.write(self.style.SUCCESS(f'Created user for {phone_number}'))

            # Link user to member
            if member.user != user:
                member.user = user
                member.save()

            # Assign role
            user_role, created = UserRole.objects.get_or_create(
                user=user,
                role=role,
                defaults={'is_active': True}
            )

            if not created:
                # Update existing role
                user_role.is_active = True
                user_role.save()
                self.stdout.write(self.style.SUCCESS(f'Updated role for {phone_number} to {role}'))
            else:
                self.stdout.write(self.style.SUCCESS(f'Assigned role {role} to {phone_number}'))

            self.stdout.write(self.style.SUCCESS(f'User: {user.username} ({user.first_name} {user.last_name})'))

        except Member.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'No member found with phone number {phone_number}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
