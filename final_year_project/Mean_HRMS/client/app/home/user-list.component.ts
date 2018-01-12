import { Component, OnInit } from '@angular/core';
import { User } from '../_models/index';
import { UserService } from '../_services/index';
import { Router } from '@angular/router';

@Component({
    moduleId: module.id,
	selector:'user-list',
    templateUrl: 'user-list.component.html'
})

export class UserListComponent implements OnInit {
    currentUser: User;
    users: User[] = [];
	
	constructor(private router: Router, private userService: UserService) {
		this.currentUser = JSON.parse(localStorage.getItem('currentUser'));
    }
	
    ngOnInit() {
        this.loadAllUsers();
    }

    deleteUser(_id: string) {
        this.userService.delete(_id).subscribe(() => { this.loadAllUsers() });
    }
	
	editUser(_id: string) {
		this.router.navigate(['/editUser',_id]);
	}
	
    private loadAllUsers() {
        this.userService.getAll().subscribe(users => { this.users = users; });
    }
}