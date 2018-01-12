import { Injectable } from '@angular/core';
import { Http, Headers, RequestOptions, Response } from '@angular/http';

import { AppConfig } from '../app.config';
import { Holiday } from '../_models/index';

@Injectable()
export class HolidayService{
	constructor(private http: Http, private config: AppConfig) { }

	getAll() {
        return this.http.get(this.config.apiUrl + '/holidays',this.jwt()).map((response: Response) => response.json());

    }

    create(holiday: Holiday) {
        return this.http.post(this.config.apiUrl + '/holidays/register', holiday , this.jwt());
        
    }
 
     // private helper methods

    private jwt() {
        // create authorization header with jwt token
        let currentUser = JSON.parse(localStorage.getItem('currentUser'));
        if (currentUser && currentUser.token) {
            let headers = new Headers({ 'Authorization': 'Bearer ' + currentUser.token });
            return new RequestOptions({ headers: headers });
        }
    }
}