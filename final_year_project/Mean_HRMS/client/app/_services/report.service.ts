import { Injectable } from '@angular/core';
import { Http, Headers, RequestOptions, Response } from '@angular/http';

import { AppConfig } from '../app.config';
import { Report } from '../_models/index';

@Injectable()
export class ReportService{
	constructor(private http: Http, private config: AppConfig) { 

	}

	dataSend(report : Report){
            return this.http.post(this.config.apiUrl + '/users/report' + report, this.jwt());

    }

    get_report(){
        return this.http.get(this.config.apiUrl + '/users', this.jwt()).map((response: Response) => response.json());

    }


  	private jwt() {
        // create authorization header with jwt token
        let currentUser = JSON.parse(localStorage.getItem('currentUser'));
        if (currentUser && currentUser.token) {
            let headers = new Headers({ 'Authorization': 'Bearer ' + currentUser.token });
            return new RequestOptions({ headers: headers });
        }
    }
}